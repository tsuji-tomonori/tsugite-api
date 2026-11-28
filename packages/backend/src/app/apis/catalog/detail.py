"""商品の詳細を取得する。"""

import json

from app.core.catalog import listing, record
from app.core.credential_policy import individual
from app.core.diagnostics import asset_object
from app.core.offers import configured, describe
from app.core.publication import publication_policy, reviewer
from app.core.releases import history
from app.core.workspace import allowed_audience
from app.dependencies import DB, User
from app.schemas.catalog import Detail
from app.schemas.errors import domain_errors
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from tsugite_db.models import Access, Event, Member, MemberProfile

router = APIRouter()


#: APIの詳細と公開仕様を取得する
@router.get(
    "/apis/{key}", responses=domain_errors(403, 404, 503), response_model=Detail, operation_id="detail"
)
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
    can_review = reviewer(a, actor)
    if not can_review and not allowed_audience(a, actor):
        raise HTTPException(404)
    if not a.published and a.owner not in actor.owners and not grant and not can_review:
        raise HTTPException(404)
    contact = db.get(Member, a.responsible) if a.responsible else None
    profile = db.get(MemberProfile, a.responsible) if contact else None
    summary = listing(a)
    steps = []
    outcome = None
    reason = ""
    if a.owner in actor.owners and not a.published:
        if a.publication_request:
            pending = json.loads(a.publication_request)
            steps = pending.get("steps", [])
            if not steps:
                # 旧形式の申請も提出時の監査記録から元の順番を復元する。
                submitted = db.scalar(
                    select(Event.detail)
                    .where(Event.asset_id == key, Event.action == "publication.submit")
                    .order_by(Event.at.desc(), Event.id.desc())
                    .limit(1)
                )
                remaining = pending["remaining"]
                original = submitted.split(" → ") if submitted else []
                if original[-len(remaining) :] == remaining:
                    steps = original
                    summary.publication_total = len(original)
                    summary.publication_position = len(original) - len(remaining) + 1
        else:
            steps = publication_policy(db).steps
            last = db.execute(
                select(Event.action, Event.detail)
                .where(
                    Event.asset_id == key,
                    Event.action.in_(
                        ("edit", "unpublish", "publication.reject", "publication.withdraw")
                    ),
                )
                .order_by(Event.at.desc(), Event.id.desc())
                .limit(1)
            ).first()
            if last and last.action == "publication.reject":
                outcome = "rejected"
                reason = last.detail.partition(" ")[2]
            elif last and last.action == "publication.withdraw":
                outcome = "withdrawn"
    return Detail(
        responsible_label=(profile.full_name if profile else None)
        or (contact.username if contact else a.responsible)
        or a.owner,
        **summary.model_dump(),
        publication_steps=steps,
        publication_outcome=outcome,
        publication_reason=reason,
        can_review_publication=can_review,
        publication_guidelines=json.loads(a.publication_request)["guidelines"]
        if a.publication_request
        else "",
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
