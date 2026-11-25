# サンプルAPIが参照するSQLiteのデータを準備する。
"""商品ごとに固定の見本データを持つ読み取り専用SQLite。"""

import sqlite3
from functools import cached_property
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class InternalServerError(BaseModel):
    error_code: Literal["INTERNAL_ERROR"]
    detail: str


class MissingRecord(BaseModel):
    detail: str


class MissingStock(BaseModel):
    message: str


class ProductAPI(FastAPI):
    def openapi(self):
        document = super().openapi()
        for item in document["paths"].values():
            for op in item.values():
                params = op.get("parameters", [])
                # An unconstrained string detail key reaches the SQLite lookup (200 or 404).
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


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class SampleDatabase:
    def __init__(self, schema: str, rows: list[tuple]):
        self.schema = schema
        self.rows = rows

    @cached_property
    def connection(self):
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute(self.schema)
        placeholders = ", ".join("?" for _ in self.rows[0])
        db.executemany(f"INSERT INTO records VALUES ({placeholders})", self.rows)
        db.commit()
        db.execute("PRAGMA query_only = ON")
        return db

    def all(self, query, *params):
        return [dict(row) for row in self.connection.execute(query, params)]

    def one(self, query, *params):
        row = self.connection.execute(query, params).fetchone()
        if row is None:
            raise HTTPException(404, "該当するデータがありません")
        return dict(row)

    def app(self, title, description):
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
            self.connection.execute("SELECT 1 FROM records LIMIT 1").fetchone()
            return Health()

        return app
