from app.apis.catalog.common import DB, User, event, record, right_id
from app.apis.catalog.offers import submission
from app.apis.schemas import Apply, Right
from app.core.diagnostics import asset_object
from app.core.workspace import allowed_audience, policy, private_project, stopped
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import update
from tsugite_db.models import Access, Asset

router = APIRouter()


#: 特定の環境でのAPI利用を申請する
@router.post("/apis/{key}/requests", status_code=201, response_model=Right, operation_id="apply")
def apply(
    #: カタログ掲載APIの識別子
    key: str,
    data: Apply,
    request: Request,
    actor: User,
    db: DB,
):
    if data.project not in actor.projects and not (
        data.personal and data.project == private_project(actor.subject)
    ):
        raise HTTPException(403)
    asset = record(db, key)
    if not allowed_audience(asset, actor):
        raise HTTPException(404)
    if stopped(db, actor, data.project):
        raise HTTPException(403, "利用停止中です")
    if not asset.published or data.environment not in asset_object(asset, "targets"):
        raise HTTPException(409, "対象のAPIまたは環境は申請できません")
    key_id = right_id(key, data.project, data.environment, actor.subject if data.personal else "")
    grant = db.get(Access, key_id)
    if grant is None:
        grant = Access(id=key_id, asset_id=key, project=data.project, environment=data.environment)
        db.add(grant)
    elif grant.status in {"pending", "approved"}:
        raise HTTPException(409, "同じ環境への申請または利用権限がすでにあります")
    grant.submission, route, grant.stage = submission(asset, data, actor)
    # Serialize the validated offer with edits that close existing grants. A concurrent
    # request must not insert a live grant under terms that have just been replaced.
    guard = (
        update(Asset)
        .where(Asset.id == key, Asset.revision == asset.revision)
        .values(published=Asset.published)
        .returning(Asset.id)
    )
    with db.no_autoflush:
        if db.scalar(guard) is None:
            raise HTTPException(409, "利用条件が変更されました。再読み込みしてください")
    grant.status = "pending"
    grant.subject = actor.subject if data.personal else None
    grant.applicant = actor.subject
    grant.decision_note = None
    grant.reason = data.reason
    event(db, request, actor, asset, "apply", data.project, data.environment, data.reason)
    rules = policy(asset)
    if (
        route == "auto"
        or route == "legacy"
        and (
            actor.departments.intersection(rules.get("auto_departments", []))
            or actor.titles.intersection(rules.get("auto_titles", []))
        )
    ):
        grant.status = "approved"
        note = "提供者の自動承認条件に一致"
        grant.decision_note = note
        event(db, request, actor, asset, "approve", data.project, data.environment, note)
    db.commit()
    return grant
