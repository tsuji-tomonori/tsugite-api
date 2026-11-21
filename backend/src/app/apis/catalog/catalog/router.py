import json

from app.apis.catalog.common import DB, User, listing
from app.apis.catalog.search_rank import rank_assets
from app.apis.schemas import CatalogPage, Env, Listing
from app.core.workspace import allowed_audience
from app.db.models import Asset
from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import defer

router = APIRouter()


def collection(db, actor, inventory, q, environment=None):
    stmt = select(Asset).where(
        Asset.removed_at.is_(None),
        Asset.owner.in_(actor.owners) if inventory else Asset.published.is_(True),
    )
    if not q.strip():
        stmt = stmt.options(defer(Asset.spec))
    eligible = [
        a
        for a in db.scalars(stmt)
        if allowed_audience(a, actor) and (not environment or environment in json.loads(a.targets))
    ]
    return rank_assets(eligible, q)


@router.get("/apis", response_model=list[Listing], operation_id="catalog")
def catalog(actor: User, db: DB, q: str = Query("", max_length=120), inventory: bool = False):
    return [listing(a) for a in collection(db, actor, inventory, q)]


@router.get("/catalog-page", response_model=CatalogPage, operation_id="catalogPage")
def catalog_page(
    actor: User,
    db: DB,
    q: str = Query("", max_length=120),
    inventory: bool = False,
    environment: Env | None = None,
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
