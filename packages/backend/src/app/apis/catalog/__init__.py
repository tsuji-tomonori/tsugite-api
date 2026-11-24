# カタログ操作のルーターを登録する。
from fastapi import APIRouter

from .apply.router import router as apply_router
from .audit.router import router as audit_router
from .catalog.router import router as catalog_router
from .decide.router import router as decide_router
from .detail.router import router as detail_router
from .me.router import router as me_router
from .publish.router import router as publish_router
from .register.router import router as register_router
from .requests.router import router as requests_router

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
