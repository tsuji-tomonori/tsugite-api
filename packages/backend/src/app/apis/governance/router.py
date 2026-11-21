from fastapi import APIRouter

from . import alerts, directory, keys, members, notifications, observability, policies

router = APIRouter()
for feature in (alerts, directory, keys, members, notifications, observability, policies):
    router.include_router(feature.router)
