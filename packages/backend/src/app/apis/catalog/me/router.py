from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.core.workspace import private_project, units, workspace_targets
from fastapi import APIRouter

router = APIRouter()


#: ログイン中の利用者の所属と権限を確認する
@router.get("/me", operation_id="me", responses={200: {"model": outputs.Profile}})
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
            for k, v in workspace_targets(db).items()
            if v.owner in actor.owners
        },
    }
