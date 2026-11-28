"""API呼び出しの記録を保存する。"""

import os
import secrets
from uuid import uuid4

from app.core.diagnostics import OperationalRepair, emit
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from starlette.routing import Match


def install_request_logs(app):
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = (
            request.scope.get("aws.event", {}).get("requestContext", {}).get("requestId") or uuid4().hex
        )
        fields = {}
        try:
            if os.getenv("AWS_LAMBDA_FUNCTION_NAME") and not secrets.compare_digest(
                request.headers.get("x-tsugite-origin", ""), os.environ["ORIGIN_SECRET"]
            ):
                fields["reason"] = "origin_denied"
                result = JSONResponse({"detail": "入口を確認してください"}, 403)
            else:
                result = await call_next(request)
        except Exception as exc:
            fields.update(reason=type(exc).__name__, failed=True)
            result = JSONResponse(
                {"error_code": "INTERNAL_ERROR", "detail": "サーバーでエラーが発生しました"}, 500
            )
        result.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"] = "no-store"
            route = getattr(request.scope.get("route"), "path", None)
            params = request.path_params
            if fields.get("reason") == "origin_denied":
                for candidate in app.routes:
                    match, scope = candidate.matches(request.scope)
                    if match is Match.FULL:
                        route = getattr(scope.get("route", candidate), "path", None)
                        params = scope.get("path_params", {})
                        break
            if route and route.startswith("/") and not route.startswith("/api/"):
                route = "/api" + route
            if route and route.startswith(
                ("/api/apis/{key}", "/api/invoke/{key}", "/api/requests/{key}")
            ):
                fields["asset_id"] = params.get("key")
            fields.update(getattr(request.state, "diagnostics", {}))
            emit(
                "http.access",
                source="api",
                status=result.status_code,
                request_id=request.state.request_id,
                method=request.method,
                route=route,
                operation=getattr(request.state, "operation", None),
                screen=request.headers.get("x-tsugite-screen"),
                actor_id=getattr(request.state, "actor_id", None),
                target_subject_id=getattr(request.state, "target_subject_id", params.get("subject")),
                **fields,
            )
        return result

    @app.exception_handler(OperationalRepair)
    async def repair(request, exc):
        request.state.diagnostics = exc.fields
        return JSONResponse({"detail": exc.detail}, exc.status_code)

    @app.exception_handler(StaleDataError)
    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        code = getattr(getattr(exc, "orig", None), "sqlstate", None)
        request.state.diagnostics = {
            "reason": type(exc).__name__,
            "failed": isinstance(exc, IntegrityError) and code not in (None, "23505"),
        }
        return JSONResponse({"detail": "同時に更新されました。状態を再確認してください"}, 409)

    @app.exception_handler(OperationalError)
    async def db_error(request, exc):
        code = getattr(exc.orig, "sqlstate", "")
        request.state.diagnostics = {"reason": "database_" + (code or "unavailable"), "failed": True}
        status = 409 if code in {"40001", "OC000", "OC001"} else 503
        return JSONResponse({"detail": "状態を再確認してから再実行してください"}, status)
