"""ヘルスチェックとエラー応答の形式を定義する。"""

from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class InternalServerError(BaseModel):
    error_code: Literal["INTERNAL_ERROR"]
    detail: str


class MissingRecord(BaseModel):
    detail: str


class MissingStock(BaseModel):
    message: str
