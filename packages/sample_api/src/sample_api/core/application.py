"""各商品のFastAPIアプリに共通のヘルスチェックとエラー応答を登録する。"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import Health, InternalServerError


class ProductAPI(FastAPI):
    def openapi(self):
        document = super().openapi()
        for item in document["paths"].values():
            for op in item.values():
                params = op.get("parameters", [])
                # 制約のない文字列のパス引数は必ずSQLiteの検索に進む。
                if (
                    params
                    and "requestBody" not in op
                    and all(
                        p["in"] == "path"
                        and p["schema"].get("type") == "string"
                        and not (p["schema"].keys() - {"type", "title", "description"})
                        for p in params
                    )
                ):
                    validation = (
                        op["responses"].get("422", {}).get("content", {}).get("application/json", {})
                    )
                    if validation.get("schema") == {"$ref": "#/components/schemas/HTTPValidationError"}:
                        del op["responses"]["422"]
        return document


def create_product_app(db: SampleDatabase, title: str, description: str) -> FastAPI:
    app = ProductAPI(
        title=title,
        description=description,
        version="1.0.0",
        responses={500: {"model": InternalServerError, "description": "サーバー内部のエラー"}},
    )

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return JSONResponse(
            {"error_code": "INTERNAL_ERROR", "detail": "サーバーでエラーが発生しました"}, 500
        )

    @app.get("/health", summary="データベースの稼働状態を確認")
    def health() -> Health:
        db.connection.execute("SELECT 1 FROM records LIMIT 1").fetchone()
        return Health()

    return app
