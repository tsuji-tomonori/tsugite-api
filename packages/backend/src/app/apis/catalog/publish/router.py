from app.apis.catalog.common import DB, User, event, listing, record
from app.apis.catalog.releases import record_release
from app.apis.schemas import Listing
from app.core.config import targets
from app.core.diagnostics import asset_object
from app.integrations.upstream import probe
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


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
            bindings = targets()
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
