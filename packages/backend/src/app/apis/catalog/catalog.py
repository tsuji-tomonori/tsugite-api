# 商品カタログを検索する。
from app.core.catalog import listing
from app.core.catalog_rank import rank_assets
from app.core.catalog_visibility import visible_collection
from app.dependencies import DB, User
from app.schemas.catalog import CatalogPage, Env, Listing
from fastapi import APIRouter, Query

router = APIRouter()


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
