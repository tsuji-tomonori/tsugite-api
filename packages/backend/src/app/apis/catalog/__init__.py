from fastapi import APIRouter

from .apply import router as apply_router
from .audit import router as audit_router
from .catalog import router as catalog_router
from .decide import router as decide_router
from .detail import router as detail_router
from .me import router as me_router
from .publish import router as publish_router
from .register import router as register_router
from .requests import router as requests_router

router = APIRouter()
router.include_router(me_router)
router.include_router(catalog_router)
router.include_router(register_router)
router.include_router(detail_router)
router.include_router(publish_router)
router.include_router(apply_router)
router.include_router(requests_router)
router.include_router(decide_router)
router.include_router(audit_router)
