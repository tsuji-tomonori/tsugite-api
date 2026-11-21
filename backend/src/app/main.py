import logging
import os
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError

from app.apis import catalog, gateway
from app.core.auth import demo_token
from app.core.config import local_demo, settings

log=logging.getLogger("tsugite.access")


def create_app() -> FastAPI:
    app=FastAPI(title="継手API",version="0.1.0",docs_url=None,redoc_url=None,openapi_url="/api/openapi.json" if local_demo() else None)

    @app.middleware("http")
    async def request_context(request: Request,call_next):
        request.state.request_id=request.scope.get("aws.event",{}).get("requestContext",{}).get("requestId") or uuid4().hex
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            secret=os.environ["ORIGIN_SECRET"]
            if not secrets.compare_digest(request.headers.get("x-tsugite-origin",""),secret):
                return JSONResponse({"detail":"入口を確認してください"},403)
        result=await call_next(request)
        result.headers["X-Request-ID"]=request.state.request_id
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"]="no-store"
        log.info("request_id=%s method=%s status=%s",request.state.request_id,request.method,result.status_code)
        return result

    @app.exception_handler(StaleDataError)
    @app.exception_handler(IntegrityError)
    async def conflict(request,exc):
        return JSONResponse({"detail":"同時に更新されました。状態を再確認してください"},409)

    @app.exception_handler(OperationalError)
    async def db_error(request,exc):
        code=getattr(exc.orig,"sqlstate","")
        status=409 if code in {"40001","OC000","OC001"} else 503
        return JSONResponse({"detail":"状態を再確認してから再実行してください"},status)

    @app.get("/api/health")
    def health():
        return {"status":"ok"}

    @app.get("/api/config")
    def config():
        cfg=settings()
        return {"demo":local_demo(),"domain":cfg.get("domain",""),"client_id":cfg.get("portal_client","")}

    if local_demo():
        @app.post("/api/demo/{persona}")
        def local_login(persona: str,request: Request):
            if request.headers.get("origin") and request.headers["origin"]!=str(request.base_url).rstrip("/"):
                raise HTTPException(403)
            return {"access_token":demo_token(persona)}

    app.include_router(catalog.router,prefix="/api")
    app.include_router(gateway.router,prefix="/api")
    static=Path(os.getenv("FRONTEND_DIST","frontend/dist"))
    if static.is_dir() and not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        app.mount("/",StaticFiles(directory=static,html=True),name="portal")
    return app


app=create_app()
handler=Mangum(app,lifespan="off")
