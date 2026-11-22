from fastapi import APIRouter

from . import (
    alerts,
    credential_settings,
    credentials,
    directory,
    keys,
    members,
    notifications,
    observability,
    policies,
)

router = APIRouter()
for feature in (
    alerts,
    credential_settings,
    credentials,
    directory,
    keys,
    members,
    notifications,
    observability,
    policies,
):
    router.include_router(feature.router)
