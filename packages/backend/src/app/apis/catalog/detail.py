from app.core.catalog import listing, record
from app.core.credential_policy import individual
from app.core.diagnostics import asset_object
from app.core.offers import configured, describe
from app.core.releases import history
from app.core.workspace import allowed_audience
from app.dependencies import DB, User
from app.schemas.catalog import Detail
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from tsugite_db.models import Access

router = APIRouter()


#: APIの詳細と公開仕様を取得する
@router.get("/apis/{key}", response_model=Detail, operation_id="detail")
def detail(
    #: カタログ掲載APIの識別子
    key: str,
    actor: User,
    db: DB,
):
    a = record(db, key)
    grant = db.scalar(
        select(Access.id)
        .where(
            Access.asset_id == key,
            (
                (Access.subject.is_(None) & Access.project.in_(actor.projects))
                | (Access.subject == actor.subject)
            ),
            Access.status == "approved",
        )
        .limit(1)
    )
    if not allowed_audience(a, actor):
        raise HTTPException(404)
    if not a.published and a.owner not in actor.owners and not grant:
        raise HTTPException(404)
    return Detail(
        **listing(a).model_dump(),
        suspended=bool(a.suspended),
        spec=asset_object(a, "spec"),
        offers={
            env: describe(rule, a.revision, a.owner in actor.owners)
            for env, rule in configured(a).items()
        },
        release_note=a.release_note or "",
        releases=history(db, a),
        allowed_operations=individual(db, key, actor.subject),
        base_path=a.base_path or "",
        bindings=asset_object(a, "targets") if a.owner in actor.owners else {},
    )
