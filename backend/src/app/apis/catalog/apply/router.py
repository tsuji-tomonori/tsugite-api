import json

from app.apis.catalog.common import DB, User, event, record, right_id
from app.apis.schemas import Apply, Right
from app.core.workspace import allowed_audience, policy, private_project, stopped
from app.db.models import Access
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post("/apis/{key}/requests", status_code=201, response_model=Right, operation_id="apply")
def apply(key: str, data: Apply, request: Request, actor: User, db: DB):
    if data.project not in actor.projects and not (
        data.personal and data.project == private_project(actor.subject)
    ):
        raise HTTPException(403)
    asset = record(db, key)
    if not allowed_audience(asset, actor):
        raise HTTPException(404)
    if stopped(db, actor, data.project):
        raise HTTPException(403, "利用停止中です")
    if not asset.published or data.environment not in json.loads(asset.targets):
        raise HTTPException(409, "対象のAPIまたは環境は申請できません")
    key_id = right_id(key, data.project, data.environment, actor.subject if data.personal else "")
    grant = db.get(Access, key_id)
    if grant is None:
        grant = Access(id=key_id, asset_id=key, project=data.project, environment=data.environment)
        db.add(grant)
    elif grant.status in {"pending", "approved"}:
        raise HTTPException(409, "同じ環境への申請または利用権限がすでにあります")
    grant.status = "pending"
    grant.subject = actor.subject if data.personal else None
    grant.applicant = actor.subject
    grant.decision_note = None
    grant.reason = data.reason
    event(db, request, actor, asset, "apply", data.project, data.environment, data.reason)
    rules = policy(asset)
    if actor.departments.intersection(rules.get("auto_departments", [])) or actor.titles.intersection(
        rules.get("auto_titles", [])
    ):
        grant.status = "approved"
        note = "提供者の自動承認条件に一致"
        grant.decision_note = note
        event(db, request, actor, asset, "approve", data.project, data.environment, note)
    db.commit()
    return grant
