# 商品を公開する。
import json

from app.apis.governance.directory import audit
from app.core.catalog import event, listing, record
from app.core.diagnostics import asset_object
from app.core.publication import publication_policy, reviewer, validate_steps
from app.core.releases import record_release
from app.core.workspace import workspace_targets
from app.dependencies import DB, User
from app.integrations.upstream import probe
from app.schemas.catalog import Listing, PublicationDecision, PublicationPolicy
from app.schemas.errors import domain_errors
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import defer
from tsugite_db.models import Asset, DirectoryTree

router = APIRouter()


#: 管理者が対象APIの呼び出しを全環境で停止または再開する
@router.put("/apis/{key}/suspension", response_model=Listing, operation_id="set_suspension")
def set_suspension(
    #: 対象APIの識別子
    key: str,
    #: 全環境の呼び出しを停止するか
    suspended: bool,
    request: Request,
    actor: User,
    db: DB,
):
    if not actor.admin:
        raise HTTPException(403)
    asset = record(db, key)
    if bool(asset.suspended) != suspended:
        asset.suspended = suspended
        event(db, request, actor, asset, "invoke.suspend" if suspended else "invoke.resume")
        db.commit()
    return listing(asset)


#: APIの公開・掲載取り下げを切り替える
@router.put(
    "/apis/{key}/publication",
    responses=domain_errors(403, 404, 503),
    response_model=Listing,
    operation_id="publish",
)
def publish(
    #: カタログ掲載APIの識別子
    key: str,
    #: カタログで公開するか
    published: bool,
    request: Request,
    actor: User,
    db: DB,
):
    a = record(db, key)
    if a.owner not in actor.owners:
        raise HTTPException(403)
    if published and not a.published and not a.publication_request:
        rules = publication_policy(db)
        validate_steps(db, rules.steps)
        if "department" in rules.steps and not actor.departments:
            raise HTTPException(422, "公開申請には所属部署の登録が必要です")
        a.publication_request = json.dumps(
            {
                "applicant": actor.subject,
                "remaining": rules.steps,
                "departments": sorted(actor.departments),
                "guidelines": rules.guidelines,
            },
            ensure_ascii=False,
        )
        event(db, request, actor, a, "publication.submit", a.owner, detail=" → ".join(rules.steps))
    elif not published and (a.published or a.publication_request):
        action = "unpublish" if a.published else "publication.withdraw"
        a.published = False
        a.publication_request = None
        event(db, request, actor, a, action, a.owner)
    db.commit()
    return listing(a)


#: 提供ガイドラインと公開に必要な承認順を取得する
@router.get("/publication-policy", response_model=PublicationPolicy)
def read_publication_policy(actor: User, db: DB):
    return publication_policy(db)


#: 管理者が提供ガイドラインと今後の公開申請の承認順を設定する
@router.put("/publication-policy", response_model=PublicationPolicy, responses=domain_errors(409, 503))
def configure_publication_policy(data: PublicationPolicy, request: Request, actor: User, db: DB):
    if not actor.admin:
        raise HTTPException(403)
    data.steps = validate_steps(db, data.steps)
    row = db.get(DirectoryTree, "publication")
    if data.revision != (row.revision if row else 0):
        raise HTTPException(409, "提供ガイドラインが更新されました。再読み込みしてください")
    encoded = data.model_dump_json(exclude={"revision"})
    if row is None:
        db.add(DirectoryTree(id="publication", units=encoded))
    else:
        row.units = encoded
    audit(db, actor, request, "publication.policy", "", " → ".join(data.steps))
    db.commit()
    return publication_policy(db)


#: 自分が現在審査できる公開申請を一覧する
@router.get("/publication-requests", response_model=list[Listing])
def publication_requests(actor: User, db: DB):
    rows = db.scalars(
        select(Asset)
        .options(defer(Asset.spec))
        .where(Asset.publication_request.is_not(None), Asset.removed_at.is_(None))
    )
    return [listing(asset) for asset in rows if reviewer(asset, actor)]


#: 公開申請の現在の段階を承認または却下する
@router.post(
    "/apis/{key}/publication-decisions",
    response_model=Listing,
    responses=domain_errors(403, 404, 409, 502, 503),
)
def decide_publication(
    #: 公開申請の対象商品
    key: str,
    data: PublicationDecision,
    request: Request,
    actor: User,
    db: DB,
):
    a = record(db, key)
    if not a.publication_request or data.revision != a.revision:
        raise HTTPException(409, "公開申請が更新されました。再読み込みしてください")
    if not reviewer(a, actor):
        raise HTTPException(403)
    pending = json.loads(a.publication_request)
    stage = pending["remaining"].pop(0)
    a.publication_request = None
    event(
        db,
        request,
        actor,
        a,
        "publication.approve" if data.approved else "publication.reject",
        a.owner,
        detail=stage + " " + data.reason,
    )
    if data.approved and pending["remaining"]:
        a.publication_request = json.dumps(pending, ensure_ascii=False)
    elif data.approved:
        bindings = workspace_targets(db)
        for env, name in asset_object(a, "targets").items():
            if name not in bindings or (bindings[name].owner, bindings[name].environment) != (
                a.owner,
                env,
            ):
                raise HTTPException(409, "接続設定を確認してください")
            probe(bindings[name])
        record_release(db, a)
        a.published = True
        event(db, request, actor, a, "publish", a.owner)
    db.commit()
    return listing(a)
