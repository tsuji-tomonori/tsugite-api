# 管理機能のルーターを集約する。
from fastapi import APIRouter

from . import (
    alerts,
    credential_settings,
    credentials,
    directory,
    keys,
    members,
    metadata,
    notifications,
    observability,
    policies,
    profiles,
    unit_lifecycle,
)

router = APIRouter()
for feature in (
    alerts,
    credential_settings,
    credentials,
    directory,
    keys,
    members,
    metadata,
    notifications,
    observability,
    policies,
    profiles,
    unit_lifecycle,
):
    router.include_router(feature.router)
