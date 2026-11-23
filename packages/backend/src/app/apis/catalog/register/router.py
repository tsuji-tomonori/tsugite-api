import json

from app.apis import outputs
from app.apis.catalog.common import DB, User, allowed_spec, event, listing, record
from app.apis.catalog.offers import configured
from app.apis.catalog.releases import record_release
from app.apis.schemas import Listing, NewListing, Offer, Register
from app.core.diagnostics import asset_object
from app.core.workspace import units, workspace_targets
from app.integrations.spec_archive import archive_spec, canonical
from fastapi import APIRouter, HTTPException, Request
from openapi_spec_validator import validate
from sqlalchemy import select
from tsugite_db.models import Access, Asset, AssetRoute, new_id, now

router = APIRouter()


def assign_slug(db, asset: Asset, slug: str) -> None:
    if asset.route:
        if asset.route.slug != slug:
            raise HTTPException(409, "設定済みのAPI識別名は変更できません")
        return
    if db.scalar(select(AssetRoute.asset_id).where(AssetRoute.slug == slug)) is not None:
        raise HTTPException(409, "このAPI識別名はすでに使われています")
    asset.route = AssetRoute(slug=slug)


def validated_spec(data, db):
    if data.offers is not None:
        tree = units(db)
        for offer in data.offers.values():
            if any(
                step.startswith("unit/") and tree.get(step[5:], {}).get("kind") != "department"
                for step in offer.steps
            ):
                raise HTTPException(422, "承認先の部署を確認してください")
        if data.offers.keys() - data.targets.keys():
            raise HTTPException(422, "利用条件には出品する環境を指定してください")
        if len(canonical(data.model_dump()["offers"])) > 120000:
            raise HTTPException(422, "環境ごとの申請条件は合計120KB以内で指定してください")
    bindings = workspace_targets(db)
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


#: APIをカタログに登録する
@router.post("/apis", response_model=Listing, status_code=201, operation_id="register")
def register(data: NewListing, request: Request, actor: User, db: DB):
    if data.owner not in actor.owners:
        raise HTTPException(403, "提供プロジェクトの権限が必要です")
    spec = validated_spec(data, db)
    row = Asset(
        id=new_id(),
        name=data.name,
        summary=data.summary,
        owner=data.owner,
        base_path=data.base_path,
        targets=json.dumps(data.targets),
        spec=spec,
        offers=json.dumps(data.model_dump()["offers"] or {}, ensure_ascii=False),
        release_note=data.release_note,
        published=False,
    )
    assign_slug(db, row, data.slug)
    db.add(row)
    db.flush()
    archive_spec(row.id, data.spec)
    event(db, request, actor, row, "register", row.owner)
    db.commit()
    return listing(row)


#: APIの登録内容を更新する
@router.put("/apis/{key}", response_model=Listing)
def edit(
    #: カタログ掲載APIの識別子
    key: str,
    #: 変更前の版番号
    revision: int,
    data: Register,
    request: Request,
    actor: User,
    db: DB,
):
    row = record(db, key)
    if row.owner not in actor.owners or data.owner != row.owner:
        raise HTTPException(403)
    if row.revision != revision:
        raise HTTPException(409, "別の変更が入りました")
    spec = validated_spec(data, db)
    if data.slug is not None:
        assign_slug(db, row, data.slug)
        db.flush()
    structural = (asset_object(row, "spec"), asset_object(row, "targets"), row.base_path or "") != (
        data.spec,
        data.targets,
        data.base_path,
    )
    previous = configured(row)
    offers = data.model_dump()["offers"]
    if offers is None:
        offers = {env: rule for env, rule in previous.items() if env in data.targets}
    inherited = Offer.model_validate({"route": "legacy"}).model_dump()
    changed = {
        env
        for env in previous.keys() | offers.keys()
        if previous.get(env, inherited) != offers.get(env, inherited)
    }
    if row.published and (structural or data.release_note != (row.release_note or "")):
        record_release(db, row)
    if structural:
        archive_spec(row.id, data.spec)
        row.published = False
        close_rights(db, request, actor, row, "接続先または仕様が変更されました")
    elif changed:
        close_rights(db, request, actor, row, "この環境の利用条件が変更されました", changed)
    if changed or data.release_note != (row.release_note or ""):
        row.published = False
    row.offers = json.dumps(offers, ensure_ascii=False)
    row.release_note = data.release_note
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


def close_rights(db, request, actor, row, reason, environments=None):
    for right in db.scalars(
        select(Access).where(Access.asset_id == row.id, Access.status.in_(("approved", "pending")))
    ):
        if environments is not None and right.environment not in environments:
            continue
        right.stage = None
        action = "revoke" if right.status == "approved" else "reject"
        right.decision_note = reason
        right.status = "revoked" if action == "revoke" else "rejected"
        event(db, request, actor, row, action, right.project, right.environment, reason)


#: APIをカタログから削除する（論理削除）
@router.delete("/apis/{key}", responses={200: {"model": outputs.Deleted}})
def delete(
    #: カタログ掲載APIの識別子
    key: str,
    #: 変更前の版番号
    revision: int,
    request: Request,
    actor: User,
    db: DB,
):
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
