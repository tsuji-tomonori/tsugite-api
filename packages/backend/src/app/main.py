# FastAPIアプリケーションを組み立てる。
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from app.apis import catalog, chat, gateway, inquiries, outputs
from app.apis.catalog.common import DB
from app.apis.governance import router as governance
from app.core.auth import demo_token
from app.core.config import local_demo, settings
from app.core.request_logs import install_request_logs
from app.design_names import PortalAPI


def create_app() -> FastAPI:
    app = PortalAPI(
        title="継手API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if local_demo() else None,
    )

    install_request_logs(app)

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
    app.include_router(chat.router, prefix="/api")
    app.include_router(inquiries.router, prefix="/api")
    app.include_router(gateway.router, prefix="/api")
    static = Path(os.getenv("FRONTEND_DIST", "packages/frontend/dist"))
    if static.is_dir() and not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        app.mount("/", StaticFiles(directory=static, html=True), name="portal")
    return app


app = create_app()
handler = Mangum(app, lifespan="off")
