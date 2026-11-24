from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.core.metadata import metadata_fields
from app.core.workspace import private_project, project_label, units, workspace_targets
from fastapi import APIRouter

router = APIRouter()


#: ログイン中の利用者の所属と権限を確認する
@router.get("/me", operation_id="me", responses={200: {"model": outputs.Profile}})
def me(actor: User, db: DB):
    tree = units(db) if actor.admin else {}
    projects = [key for key, unit in tree.items() if unit["kind"] == "project"]
    return {
        "metadata_fields": list(metadata_fields(db).values()),
        "metadata": {key: sorted(values) for key, values in actor.metadata.items()},
        "known_projects": projects,
        "known_project_labels": {key: project_label(tree, key) for key in projects},
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
