import json

from app.apis import outputs
from app.apis.catalog.common import DB, User, allowed_spec, event, listing, record
from app.apis.schemas import Listing, Register
from app.core.config import targets
from fastapi import APIRouter, HTTPException, Request
from openapi_spec_validator import validate
from sqlalchemy import select
from tsugite_db.models import Access, Asset, new_id, now

router = APIRouter()


def validated_spec(data):
    bindings = targets()
    for env, key in data.targets.items():
        target = bindings.get(key)
        if not target or target.owner != data.owner or target.environment != env:
            raise HTTPException(422, "プロジェクトと環境に対応する接続先を選んでください")
    spec = json.dumps(data.spec, ensure_ascii=False)
    if len(spec.encode()) > 500_000 or not allowed_spec(data.spec) or not data.spec.get("paths"):
        raise HTTPException(422, "外部参照を含まない500KB以内のOpenAPI JSONを指定してください")
    if not str(data.spec.get("openapi", "")).startswith(("3.0.", "3.1.")):
        raise HTTPException(422, "OpenAPI 3.0または3.1を指定してください")
    try:
        validate(data.spec)
    except Exception as exc:
        raise HTTPException(422, "OpenAPIの形式または内部参照を確認してください") from exc
    return spec


@router.post("/apis", response_model=Listing, status_code=201, operation_id="register")
def register(data: Register, request: Request, actor: User, db: DB):
    if data.owner not in actor.owners:
        raise HTTPException(403, "提供プロジェクトの権限が必要です")
    spec = validated_spec(data)
    row = Asset(
        id=new_id(),
        name=data.name,
        summary=data.summary,
        owner=data.owner,
        base_path=data.base_path,
        targets=json.dumps(data.targets),
        spec=spec,
        published=False,
    )
    db.add(row)
    event(db, request, actor, row, "register", row.owner)
    db.commit()
    return listing(row)


@router.put("/apis/{key}", response_model=Listing)
def edit(key: str, revision: int, data: Register, request: Request, actor: User, db: DB):
    row = record(db, key)
    if row.owner not in actor.owners or data.owner != row.owner:
        raise HTTPException(403)
    if row.revision != revision:
        raise HTTPException(409, "別の変更が入りました")
    spec = validated_spec(data)
    structural = (json.loads(row.spec), json.loads(row.targets), row.base_path or "") != (
        data.spec,
        data.targets,
        data.base_path,
    )
    if structural:
        row.published = False
        close_rights(db, request, actor, row, "接続先または仕様が変更されました")
    row.name, row.summary, row.spec, row.targets, row.base_path = (
        data.name,
        data.summary,
        spec,
        json.dumps(data.targets),
        data.base_path,
    )
    event(
        db,
        request,
        actor,
        row,
        "edit",
        row.owner,
        detail="仕様変更・再公開待ち" if structural else "掲載内容更新",
    )
    db.commit()
    return listing(row)


def close_rights(db, request, actor, row, reason):
    for right in db.scalars(
        select(Access).where(Access.asset_id == row.id, Access.status.in_(("approved", "pending")))
    ):
        action = "revoke" if right.status == "approved" else "reject"
        right.decision_note = reason
        right.status = "revoked" if action == "revoke" else "rejected"
        event(db, request, actor, row, action, right.project, right.environment, reason)


@router.delete("/apis/{key}", responses={200: {"model": outputs.Deleted}})
def delete(key: str, revision: int, request: Request, actor: User, db: DB):
    row = record(db, key)
    if row.owner not in actor.owners:
        raise HTTPException(403)
    if revision != row.revision:
        raise HTTPException(409)
    row.removed_at = now()
    row.published = False
    close_rights(db, request, actor, row, "APIが削除されました")
    event(db, request, actor, row, "delete", row.owner, detail=row.name)
    db.commit()
    return {"deleted": True}
