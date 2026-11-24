# 商品カタログを検索する。
from app.apis.catalog.common import DB, User, listing
from app.apis.schemas import CatalogPage, Env, Listing
from app.core.catalog_rank import rank_assets
from app.core.diagnostics import asset_object
from app.core.workspace import allowed_audience
from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import defer
from tsugite_db.models import Asset

router = APIRouter()


def visible_collection(db, actor, inventory=False, environment=None, *, spec=False, keys=None):
    stmt = select(Asset).where(
        Asset.removed_at.is_(None),
        Asset.owner.in_(actor.owners) if inventory else Asset.published.is_(True),
    )
    if keys is not None:
        stmt = stmt.where(Asset.id.in_(keys))
    if not spec:
        stmt = stmt.options(defer(Asset.spec))
    return [
        a
        for a in db.scalars(stmt)
        if allowed_audience(a, actor) and (not environment or environment in asset_object(a, "targets"))
    ]


def collection(db, actor, inventory, q, environment=None):
    return rank_assets(visible_collection(db, actor, inventory, environment, spec=bool(q.strip())), q)


#: カタログのAPIを検索する
@router.get("/apis", response_model=list[Listing], operation_id="catalog")
def catalog(
    actor: User,
    db: DB,
    #: 検索キーワード
    q: str = Query("", max_length=120),
    #: 自分が提供するAPIを検索するか
    inventory: bool = False,
):
    return [listing(a) for a in collection(db, actor, inventory, q)]


#: カタログのAPIをページ単位で取得する
@router.get("/catalog-page", response_model=CatalogPage, operation_id="catalogPage")
def catalog_page(
    actor: User,
    db: DB,
    #: 検索キーワード
    q: str = Query("", max_length=120),
    #: 自分が提供するAPIを検索するか
    inventory: bool = False,
    #: 提供環境
    environment: Env | None = None,
    #: ページ番号
    page: int = Query(1, ge=1, le=1000000),
):
    rows = collection(db, actor, inventory, q, environment)
    size = 12
    page = min(page, max(1, (len(rows) + size - 1) // size))
    return CatalogPage(
        items=[listing(a) for a in rows[(page - 1) * size : page * size]],
        page=page,
        page_size=size,
        total=len(rows),
    )
