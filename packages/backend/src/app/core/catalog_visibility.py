from app.core.diagnostics import asset_object
from app.core.workspace import allowed_audience
from sqlalchemy import select
from sqlalchemy.orm import defer
from tsugite_db.models import Asset


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
