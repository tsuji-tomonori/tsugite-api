from app.apis.catalog.common import DB, User
from app.core.config import targets
from app.core.workspace import private_project, units
from fastapi import APIRouter

router = APIRouter()


@router.get("/me", operation_id="me")
def me(actor: User, db: DB):
    return {
        "known_projects": [k for k, u in units(db).items() if u["kind"] == "project"]
        if actor.admin
        else [],
        "personal_project": private_project(actor.subject),
        "leads": sorted(actor.leads),
        "departments": sorted(actor.departments),
        "titles": sorted(actor.titles),
        "admin": actor.admin,
        "subject": actor.subject,
        "projects": sorted(actor.projects),
        "owners": sorted(actor.owners),
        "auditor": actor.auditor,
        "targets": {
            k: {"owner": v.owner, "environment": v.environment}
            for k, v in targets().items()
            if v.owner in actor.owners
        },
    }
