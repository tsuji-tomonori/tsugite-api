# 認証情報の発行・更新を受け付ける。
import hashlib
import hmac
import json
import secrets
from typing import Literal
from urllib.parse import parse_qsl

from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.apis.governance.credential_settings import members_for
from app.apis.governance.directory import audit, manages
from app.apis.governance.keys import KeyInput, key_assets, metadata
from app.apis.schemas import Input
from app.core import credential_policy as policy
from app.core.access_token import encode, machine_actor, may_use
from app.core.auth import check_member, identify
from app.core.workspace import populate, private_project, stopped, units
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, SecretStr
from tsugite_db.models import Asset, CredentialLease, PortalKey, new_id

router = APIRouter()


#: 認証情報の発行条件
class Issue(KeyInput):
    #: 認証方式
    mode: Literal[
        #: 短期トークン方式
        "bearer",
        #: 利用者を伴うアプリ認証
        "app",
        #: システム間認証
        "system",
    ]
    #: 希望するトークン有効期間（分）
    ttl_minutes: int = Field(60, ge=1, le=60)
    #: 発行から更新可能になるまでの時間（分）
    refresh_minutes: int | None = Field(None, ge=1, le=60)
    #: 対象のAPI操作
    operations: dict[str, list[str]] = Field(default_factory=dict)
    #: 利用を許可する利用者
    users: list[str] = Field(default_factory=list)


#: トークン交換の入力
class Exchange(Input):
    #: クライアント識別子
    client_id: str = Field(min_length=32, max_length=32)
    #: クライアントシークレット
    client_secret: SecretStr


def secret_for(key):
    secret = "tsc_" + secrets.token_urlsafe(48)
    key.digest = hashlib.sha256(secret.encode()).hexdigest()
    return secret


def unavailable():
    return HTTPException(401, "認証情報が無効です")


def mint(db, key, actor, session_channel):
    if not may_use(key, actor) or stopped(db, actor, key.project):
        raise HTTPException(403, "この認証情報を利用できません")
    if (
        session_channel == "portal"
        and key.mode == "system"
        and not manages(actor, units(db), key.project)
    ):
        raise HTTPException(403, "システム認証の管理権限が必要です")
    conf = json.loads(key.config)
    scopes = json.loads(key.scopes) or policy.approved_assets(db, key.project, actor.subject)
    limit = min(conf["ttl_minutes"], policy.effective(db, key.project, actor.departments, scopes)) * 60
    now = policy.clock()
    end = min(now + limit, actor.expires or now + limit)
    if end <= now:
        raise unavailable()
    refresh_at = min(now + conf["refresh_minutes"] * 60, end)
    issued = now
    nonce = new_id()
    if session_channel or not actor.machine:
        slot = hashlib.sha256(json.dumps([session_channel, key.id, actor.subject]).encode()).hexdigest()
        lease = db.get(CredentialLease, slot)
        if (
            lease
            and lease.generation == key.revision
            and now < min(lease.refresh_at, lease.issued + limit, lease.expires, end)
        ):
            issued, nonce = lease.issued, lease.nonce
            end = min(lease.expires, issued + limit, end)
            refresh_at = min(lease.refresh_at, end)
        else:
            if not lease:
                lease = CredentialLease(id=slot)
                db.add(lease)
            lease.generation, lease.nonce, lease.issued, lease.refresh_at, lease.expires = (
                key.revision,
                nonce,
                issued,
                refresh_at,
                end,
            )
    token = encode(
        {
            "client": key.id,
            "gen": key.revision,
            "sub": actor.subject,
            "base": sorted(actor.base_projects & {key.project}),
            "service": actor.machine,
            "iat": issued,
            "exp": end,
            "jti": nonce,
        }
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": end - now,
        "refresh_after": max(0, refresh_at - now),
        "expires_at": end,
        "refresh_at": refresh_at,
    }


#: 利用条件を指定して認証情報を発行する
@router.post(
    "/credentials",
    status_code=201,
    responses={201: {"model": outputs.IssuedBearer | outputs.IssuedClient}},
)
def issue(data: Issue, actor: User, db: DB, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if data.project not in actor.projects and not (
        data.project == private_project(actor.subject) and data.kind == "personal"
    ):
        raise HTTPException(403)
    if data.mode == "system" and (
        data.kind != "shared" or data.users or not manages(actor, units(db), data.project)
    ):
        raise HTTPException(403, "システム認証はプロジェクト管理者が共有として発行してください")
    refresh = data.refresh_minutes or max(1, data.ttl_minutes * 3 // 4)
    if refresh > data.ttl_minutes:
        raise HTTPException(422, "更新開始を有効期間内で選んでください")
    visible = {a.id for a in key_assets(actor, db)}
    selected = set(data.api_ids)
    if not selected <= visible or not set(data.operations) <= (selected or visible):
        raise HTTPException(422, "対象APIを確認してください")
    if data.users and (
        data.kind == "personal"
        and set(data.users) != {actor.subject}
        or not set(data.users)
        <= {r["subject"] for r in members_for(db, {data.project}, [actor.subject])}
    ):
        raise HTTPException(422, "対象利用者を確認してください")
    for aid, ops in data.operations.items():
        if not set(ops) <= set(policy.operations(db.get(Asset, aid))):
            raise HTTPException(422, "OpenAPIで定義された操作を選んでください")
    cap = policy.effective(
        db,
        data.project,
        actor.departments,
        selected or policy.approved_assets(db, data.project, actor.subject),
    )
    if data.ttl_minutes > cap:
        raise HTTPException(422, f"有効期間の上限は {cap} 分です")
    conf = data.model_dump(include={"ttl_minutes", "refresh_minutes", "operations", "users"})
    conf["refresh_minutes"] = refresh
    key = PortalKey(
        id=new_id(),
        project=data.project,
        kind=data.kind,
        name=data.name,
        creator=actor.subject,
        mode=data.mode,
        config=json.dumps(conf),
        created=policy.clock(),
        scopes=json.dumps(sorted(selected)),
        digest="",
    )
    secret = secret_for(key) if data.mode != "bearer" else None
    db.add(key)
    db.flush()
    extra = {"client_id": key.id, "client_secret": secret} if secret else mint(db, key, actor, "portal")
    audit(db, actor, request, "credential.issue", key.project, key.id + " " + data.mode)
    db.commit()
    return {**metadata(key), **extra}


#: ポータルから短期アクセストークンを取得する
@router.post("/credentials/{key_id}/token", responses={200: {"model": outputs.Token}})
def portal_token(
    #: 認証情報の識別子
    key_id: str,
    actor: User,
    db: DB,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    key = db.get(PortalKey, key_id)
    if not key or not key.mode or key.revoked:
        raise unavailable()
    result = mint(db, key, actor, "portal")
    audit(db, actor, request, "token.portal", key.project, key.id)
    db.commit()
    return result


ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"


#: 利用者のログイン情報を選択した認証情報の短期トークンに交換する
@router.post(
    "/credentials/{key_id}/token-exchange",
    responses={200: {"model": outputs.ExchangedToken}},
    openapi_extra={
        "x-design-auth": "フォームのsubject_tokenにログイン済み利用者のアクセストークンを指定し、本人が利用可能な認証情報に交換します。",
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "required": ["grant_type", "subject_token_type", "subject_token"],
                        "properties": {
                            "grant_type": {
                                "title": "トークン交換方式",
                                "type": "string",
                                "enum": [TOKEN_EXCHANGE],
                            },
                            "subject_token_type": {
                                "title": "交換元のトークン種別",
                                "type": "string",
                                "enum": [ACCESS_TOKEN_TYPE],
                            },
                            "subject_token": {
                                "title": "利用者のアクセストークン",
                                "type": "string",
                                "format": "password",
                            },
                            "requested_token_type": {
                                "title": "希望するトークン種別",
                                "type": "string",
                                "enum": [ACCESS_TOKEN_TYPE],
                            },
                        },
                    }
                }
            },
        },
    },
)
async def oauth_exchange(
    #: ポータルで選択した認証情報の識別子
    key_id: str,
    request: Request,
    db: DB,
    response: Response,
):
    cache = {"Cache-Control": "no-store", "Pragma": "no-cache"}

    def error(code, description, status=400):
        return JSONResponse({"error": code, "error_description": description}, status, headers=cache)

    if (
        request.headers.get("content-type", "").partition(";")[0].lower()
        != "application/x-www-form-urlencoded"
    ):
        return error("invalid_request", "フォーム形式で送信してください")
    try:
        pairs = parse_qsl((await request.body()).decode(), strict_parsing=True, max_num_fields=8)
    except ValueError:
        return error("invalid_request", "交換パラメータが不正です")
    form = dict(pairs)
    if len(form) != len(pairs) or form.keys() - {
        "grant_type",
        "subject_token_type",
        "subject_token",
        "requested_token_type",
    }:
        return error("invalid_request", "未対応または重複したパラメータです")
    if form.get("grant_type") != TOKEN_EXCHANGE:
        return error("unsupported_grant_type", "トークン交換を指定してください")
    if (
        form.get("subject_token_type") != ACCESS_TOKEN_TYPE
        or form.get("requested_token_type", ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE
        or not form.get("subject_token")
    ):
        return error("invalid_request", "利用者のアクセストークンが必要です")
    try:
        actor = populate(db, identify(form["subject_token"]))
        request.state.actor_id = actor.subject
        check_member(db, actor)
        if actor.machine:
            raise unavailable()
        issued = portal_token(key_id, actor, db, request, response)
    except HTTPException as exc:
        if exc.status_code >= 500:
            raise
        return error("invalid_grant", "利用者または認証情報を確認してください", exc.status_code)
    response.headers.update(cache)
    return {**issued, "issued_token_type": ACCESS_TOKEN_TYPE}


#: クライアント認証情報をアクセストークンに交換する
@router.post(
    "/auth/token",
    responses={200: {"model": outputs.Token}},
    openapi_extra={
        "x-design-auth": "ボディのclient_id・client_secretが必須。appでは本人のAuthorization: Bearerが必須。systemではAuthorizationを送信すると400。"
    },
)
def exchange(data: Exchange, db: DB, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    key = db.get(PortalKey, data.client_id)
    digest = hashlib.sha256(data.client_secret.get_secret_value().encode()).hexdigest()
    if (
        not key
        or key.revoked
        or key.mode not in ("app", "system")
        or not hmac.compare_digest(key.digest, digest)
    ):
        raise unavailable()
    if key.mode == "app":
        scheme, _, access = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not access:
            raise unavailable()
        actor = populate(db, identify(access))
        request.state.actor_id = actor.subject
        check_member(db, actor)
        if actor.machine:
            raise unavailable()
    else:
        if request.headers.get("authorization"):
            raise HTTPException(400, "システム認証には利用者トークンを指定しません")
        actor = machine_actor(db, key)
        request.state.actor_id = actor.subject
    result = mint(db, key, actor, "app" if key.mode == "app" else "")
    audit(db, actor, request, "token.exchange", key.project, key.id)
    db.commit()
    return result


#: クライアントシークレットを再発行する
@router.post("/credentials/{key_id}/rotate", responses={200: {"model": outputs.ClientCredential}})
def rotate(
    #: 認証情報の識別子
    key_id: str,
    actor: User,
    db: DB,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    key = db.get(PortalKey, key_id)
    if not key or key.revoked or key.mode not in ("system", "app"):
        raise HTTPException(404)
    if not (
        manages(actor, units(db), key.project)
        or (key.mode == "app" and key.creator == actor.subject and may_use(key, actor))
    ):
        raise HTTPException(403)
    secret = secret_for(key)
    audit(db, actor, request, "credential.rotate", key.project, key.id)
    db.commit()
    return {"client_id": key.id, "client_secret": secret}
