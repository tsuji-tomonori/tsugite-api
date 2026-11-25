# APIキーを発行して管理する。
import hashlib
import hmac
import json
import secrets
from dataclasses import replace
from typing import Annotated

from app.apis.governance.directory import audit, manages
from app.core import credential_policy
from app.core.access_token import resolve
from app.core.auth import Actor, bearer, check_member, identify
from app.core.catalog import record
from app.core.workspace import allowed_audience, ancestry, populate, private_project, units
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.catalog import Listing
from app.schemas.keys import KeyInput
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select
from tsugite_db.models import Access, PortalKey, new_id

router = APIRouter()


def metadata(k):
    return {
        **json.loads(k.config or "{}"),
        "mode": k.mode or "legacy",
        "id": k.id,
        "name": k.name,
        "project": k.project,
        "kind": k.kind,
        "creator": k.creator,
        "api_ids": json.loads(k.scopes),
        "revoked": k.revoked,
    }


#: 発行済みの認証情報を一覧する
@router.get("/keys", responses={200: {"model": list[outputs.KeyMetadata]}})
def list_keys(actor: User, db: DB):
    stmt = select(PortalKey)
    if not actor.admin:
        stmt = stmt.where(
            or_(
                PortalKey.creator == actor.subject,
                (PortalKey.kind == "shared") & PortalKey.project.in_(actor.projects),
            )
        )
    tree = units(db)
    return [
        {**metadata(k), "can_portal_exchange": k.mode != "system" or manages(actor, tree, k.project)}
        for k in db.scalars(stmt.order_by(PortalKey.name, PortalKey.id))
    ]


#: 認証情報の対象に選べるAPIを一覧する
@router.get("/key-assets", responses={200: {"model": list[Listing]}})
def key_assets(actor: User, db: DB):
    from app.core.catalog import listing
    from tsugite_db.models import Asset

    held = select(Access.asset_id).where(
        Access.status == "approved",
        or_(
            Access.subject == actor.subject,
            Access.subject.is_(None) & Access.project.in_(actor.projects),
        ),
    )
    rows = db.scalars(
        select(Asset)
        .where(Asset.removed_at.is_(None), or_(Asset.published.is_(True), Asset.id.in_(held)))
        .order_by(Asset.name)
    )
    return [listing(a) for a in rows if allowed_audience(a, actor)]


#: 従来方式のAPIキーを発行する
@router.post("/keys", status_code=201, responses={201: {"model": outputs.IssuedKey}})
def issue(data: KeyInput, request: Request, actor: User, db: DB):
    private = data.project == private_project(actor.subject)
    if data.project not in actor.projects and not (private and data.kind == "personal"):
        raise HTTPException(403)
    for key in set(data.api_ids):
        asset = record(db, key)
        held = db.scalar(
            select(Access.id)
            .where(
                Access.asset_id == key,
                Access.project == data.project,
                Access.status == "approved",
                or_(Access.subject.is_(None), Access.subject == actor.subject),
            )
            .limit(1)
        )
        if not (
            allowed_audience(asset, actor) and (asset.published or held or asset.owner in actor.owners)
        ):
            raise HTTPException(404)
    kid = new_id()
    secret = "tsu_" + kid + "." + secrets.token_urlsafe(36)
    k = PortalKey(
        id=kid,
        name=data.name,
        creator=actor.subject,
        project=data.project,
        kind=data.kind,
        scopes=json.dumps(sorted(set(data.api_ids))),
        created=credential_policy.clock(),
        digest=hashlib.sha256(secret.encode()).hexdigest(),
    )
    db.add(k)
    audit(db, actor, request, "key.issue", k.project, k.id)
    db.commit()
    return {**metadata(k), "secret": secret}


#: 認証情報を失効させる
@router.delete("/keys/{key}", responses={200: {"model": outputs.Revoked}})
def revoke(
    #: 失効させる認証情報の識別子
    key: str,
    request: Request,
    actor: User,
    db: DB,
):
    k = db.get(PortalKey, key)
    if not k or not (
        actor.admin
        or actor.subject == k.creator
        or (k.kind == "shared" and manages(actor, units(db), k.project))
    ):
        raise HTTPException(404)
    k.revoked = True
    audit(db, actor, request, "key.revoke", k.project, k.id)
    db.commit()
    return {"revoked": True}


def invocation_actor(db, token, headers) -> Actor:
    raw = headers.get("x-api-key", "")
    selected = headers.get("x-tsugite-key-id", "")
    if token.startswith("tst_"):
        if raw or selected:
            raise HTTPException(401)
        return resolve(db, token)
    actor = None
    if token.startswith("tsu_"):
        if raw or selected:
            raise HTTPException(401)
        raw = token
    else:
        actor = populate(db, identify(token))
        check_member(db, actor)
    if not (raw or selected):
        if actor is None:
            raise HTTPException(401)
        return actor
    if raw and selected:
        raise HTTPException(401)
    kid = raw.removeprefix("tsu_").partition(".")[0] if raw else selected
    k = db.get(PortalKey, kid) if len(kid) == 32 else None
    if (
        not k
        or k.mode
        or k.revoked
        or (raw and not hmac.compare_digest(k.digest, hashlib.sha256(raw.encode()).hexdigest()))
    ):
        raise HTTPException(401, "APIキーが無効です")
    if actor is None:
        if k.kind != "shared":
            raise HTTPException(403, "本人のアクセストークンも必要です")
        tree = units(db)
        departments = ancestry(tree, [tree.get(k.project, {}).get("parent", "")])
        actor = Actor(
            "key-" + k.id,
            frozenset([k.project]),
            frozenset(),
            False,
            True,
            departments=frozenset(departments),
        )
    elif (
        actor.machine
        or (k.kind == "personal" and actor.subject != k.creator)
        or (k.project not in actor.projects and k.project != private_project(actor.subject))
    ):
        raise HTTPException(403, "このキーを利用できません")
    return replace(actor, key_id=k.id, key_shared=k.kind == "shared")


def invoker(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Actor:
    if not credentials:
        raise HTTPException(401)
    actor = invocation_actor(db, credentials.credentials, request.headers)
    request.state.actor_id = actor.subject
    return actor
