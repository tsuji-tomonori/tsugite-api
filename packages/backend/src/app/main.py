import json
import logging
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError

from app.apis import catalog, gateway, outputs
from app.apis.catalog.common import DB
from app.apis.governance import router as governance
from app.core.auth import demo_token
from app.core.config import local_demo, settings
from app.design_names import PortalAPI

log = logging.getLogger("tsugite.access")
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.propagate = False


def create_app() -> FastAPI:
    app = PortalAPI(
        title="継手API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if local_demo() else None,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = (
            request.scope.get("aws.event", {}).get("requestContext", {}).get("requestId") or uuid4().hex
        )
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            secret = os.environ["ORIGIN_SECRET"]
            if not secrets.compare_digest(request.headers.get("x-tsugite-origin", ""), secret):
                return JSONResponse({"detail": "入口を確認してください"}, 403)
        result = await call_next(request)
        result.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"] = "no-store"
        if request.url.path.startswith("/api/"):
            log.info(
                json.dumps(
                    {
                        "event": "http.access",
                        "at": datetime.now(UTC).isoformat(),
                        "operation": getattr(request.state, "operation", None),
                        "request_id": request.state.request_id,
                        "method": request.method,
                        "route": getattr(request.scope.get("route"), "path", ""),
                        "status": result.status_code,
                    }
                )
            )
        return result

    @app.exception_handler(StaleDataError)
    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse({"detail": "同時に更新されました。状態を再確認してください"}, 409)

    @app.exception_handler(OperationalError)
    async def db_error(request, exc):
        code = getattr(exc.orig, "sqlstate", "")
        status = 409 if code in {"40001", "OC000", "OC001"} else 503
        return JSONResponse({"detail": "状態を再確認してから再実行してください"}, status)

    #: サービスの稼働状態を確認する
    @app.get("/api/health", responses={200: {"model": outputs.Health}})
    def health():
        return {"status": "ok"}

    #: ポータルのログイン設定を取得する
    @app.get("/api/config", responses={200: {"model": outputs.PortalConfig}})
    def config():
        cfg = settings()
        return {
            "demo": local_demo(),
            "domain": cfg.get("domain", ""),
            "identity_endpoint": cfg.get("issuer", "").rsplit("/", 1)[0],
            "client_id": cfg.get("portal_client", ""),
        }

    if local_demo():
        #: デモ利用者としてログインする
        @app.post("/api/demo/{persona}", responses={200: {"model": outputs.DemoToken}})
        def local_login(
            #: デモでログインする利用者名
            persona: str,
            request: Request,
            db: DB,
        ):
            if request.headers.get("origin") and request.headers["origin"] != str(
                request.base_url
            ).rstrip("/"):
                raise HTTPException(403)
            return {"access_token": demo_token(persona, db)}

    app.include_router(governance.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")
    app.include_router(gateway.router, prefix="/api")
    static = Path(os.getenv("FRONTEND_DIST", "packages/frontend/dist"))
    if static.is_dir() and not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        app.mount("/", StaticFiles(directory=static, html=True), name="portal")
    return app


app = create_app()
handler = Mangum(app, lifespan="off")
