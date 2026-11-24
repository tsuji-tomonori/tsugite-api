from app.core.catalog import event, listing, record
from app.core.diagnostics import asset_object
from app.core.releases import record_release
from app.core.workspace import workspace_targets
from app.dependencies import DB, User
from app.integrations.upstream import probe
from app.schemas.catalog import Listing
from fastapi import APIRouter, HTTPException, Request

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
@router.put("/apis/{key}/publication", response_model=Listing, operation_id="publish")
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
    if a.published != published:
        if published:
            bindings = workspace_targets(db)
            if any(
                name not in bindings
                or (bindings[name].owner, bindings[name].environment) != (a.owner, env)
                for env, name in asset_object(a, "targets").items()
            ):
                raise HTTPException(409, "接続設定を確認してください")
            for name in set(asset_object(a, "targets").values()):
                probe(bindings[name])
            record_release(db, a)
        a.published = published
        event(db, request, actor, a, "publish" if published else "unpublish", a.owner)
        db.commit()
    return listing(a)
