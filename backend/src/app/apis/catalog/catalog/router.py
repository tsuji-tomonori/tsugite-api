from app.apis.catalog.common import DB, User, listing
from app.apis.schemas import CatalogPage, Env, Listing
from app.db.models import Asset
from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import defer

router = APIRouter()


def visible_assets(actor, inventory, q):
    stmt = (
        select(Asset)
        .where(Asset.removed_at.is_(None))
        .where(Asset.owner.in_(actor.owners) if inventory else Asset.published.is_(True))
    )
    if term := q.strip():
        stmt = stmt.where(
            or_(
                *(
                    column.icontains(term, autoescape=True)
                    for column in (Asset.name, Asset.summary, Asset.owner, Asset.spec)
                )
            )
        )
    return stmt


@router.get("/apis", response_model=list[Listing], operation_id="catalog")
def catalog(actor: User, db: DB, q: str = Query("", max_length=120), inventory: bool = False):
    stmt = visible_assets(actor, inventory, q)
    return [
        listing(a) for a in db.scalars(stmt.options(defer(Asset.spec)).order_by(Asset.name, Asset.id))
    ]


@router.get("/catalog-page", response_model=CatalogPage, operation_id="catalogPage")
def catalog_page(
    actor: User,
    db: DB,
    q: str = Query("", max_length=120),
    inventory: bool = False,
    environment: Env | None = None,
    page: int = Query(1, ge=1, le=1000000),
):
    stmt = visible_assets(actor, inventory, q)
    if environment:
        stmt = stmt.where(Asset.targets.contains(f'"{environment}":'))
    size = 12
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(Asset.id).subquery())) or 0
    current = min(page, max(1, (total + size - 1) // size))
    rows = db.scalars(
        stmt.options(defer(Asset.spec))
        .order_by(Asset.name, Asset.id)
        .offset((current - 1) * size)
        .limit(size)
    )
    return CatalogPage(items=[listing(a) for a in rows], page=current, page_size=size, total=total)
