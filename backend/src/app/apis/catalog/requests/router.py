from app.apis.catalog.common import DB, User
from app.apis.schemas import Right
from app.db.models import Access, Asset
from fastapi import APIRouter
from sqlalchemy import select

router = APIRouter()


@router.get("/requests", response_model=list[Right], operation_id="requests")
def requests(actor: User, db: DB, incoming: bool = False):
    stmt = select(Access, Asset.name).join(Asset, Asset.id == Access.asset_id)
    stmt = stmt.where(Asset.owner.in_(actor.owners) if incoming else Access.project.in_(actor.projects))
    return [
        Right.model_validate(row).model_copy(update={"asset_name": name})
        for row, name in db.execute(stmt.order_by(Asset.name, Access.project, Access.environment))
    ]
