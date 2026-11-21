import hashlib
import hmac
import json
import secrets
from typing import Literal

from app.apis.catalog.common import DB, User
from app.apis.governance.credential_settings import members_for
from app.apis.governance.directory import audit, manages
from app.apis.governance.keys import KeyInput, key_assets, metadata
from app.apis.schemas import Input
from app.core import credential_policy as policy
from app.core.access_token import encode, machine_actor, may_use
from app.core.auth import check_member, identify
from app.core.workspace import populate, private_project, stopped, units
from app.db.models import Asset, CredentialLease, PortalKey, new_id
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field, SecretStr

router = APIRouter()


class Issue(KeyInput):
    mode: Literal["bearer", "app", "system"]
    ttl_minutes: int = Field(60, ge=1, le=60)
    refresh_minutes: int | None = Field(None, ge=1, le=60)
    operations: dict[str, list[str]] = Field(default_factory=dict)
    users: list[str] = Field(default_factory=list)


class Exchange(Input):
    client_id: str = Field(min_length=32, max_length=32)
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


@router.post("/credentials", status_code=201)
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


@router.post("/credentials/{key_id}/token")
def portal_token(key_id: str, actor: User, db: DB, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    key = db.get(PortalKey, key_id)
    if not key or not key.mode or key.revoked:
        raise unavailable()
    result = mint(db, key, actor, "portal")
    audit(db, actor, request, "token.portal", key.project, key.id)
    db.commit()
    return result


@router.post("/auth/token")
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
        check_member(db, actor)
        if actor.machine:
            raise unavailable()
    else:
        if request.headers.get("authorization"):
            raise HTTPException(400, "システム認証には利用者トークンを指定しません")
        actor = machine_actor(db, key)
    result = mint(db, key, actor, "app" if key.mode == "app" else "")
    audit(db, actor, request, "token.exchange", key.project, key.id)
    db.commit()
    return result


@router.post("/credentials/{key_id}/rotate")
def rotate(key_id: str, actor: User, db: DB, request: Request, response: Response):
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
