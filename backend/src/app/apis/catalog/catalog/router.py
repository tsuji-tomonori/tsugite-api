from app.apis.catalog.common import DB, User, listing
from app.apis.schemas import Listing
from app.db.models import Asset
from fastapi import APIRouter, Query
from sqlalchemy import or_, select

router = APIRouter()


@router.get("/apis", response_model=list[Listing], operation_id="catalog")
def catalog(actor: User, db: DB, q: str = Query("", max_length=120), inventory: bool = False):
    stmt = select(Asset).where(Asset.owner.in_(actor.owners) if inventory else Asset.published.is_(True))
    if q.strip():
        term = q.strip()
        stmt = stmt.where(
            or_(
                Asset.name.icontains(term, autoescape=True),
                Asset.summary.icontains(term, autoescape=True),
                Asset.owner.icontains(term, autoescape=True),
                Asset.spec.icontains(term, autoescape=True),
            )
        )
    return [listing(a) for a in db.scalars(stmt.order_by(Asset.name, Asset.id))]
