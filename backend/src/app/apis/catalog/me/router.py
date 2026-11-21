from app.apis.catalog.common import User
from app.core.config import targets
from fastapi import APIRouter

router = APIRouter()


@router.get("/me", operation_id="me")
def me(actor: User):
    return {
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
