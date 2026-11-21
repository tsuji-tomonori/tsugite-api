from fastapi import APIRouter

from . import alerts, members, notifications, observability

router = APIRouter()
for feature in (alerts, members, notifications, observability):
    router.include_router(feature.router)
