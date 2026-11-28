# credential_settings のAPIで扱う入出力モデルを定義する。
from typing import Literal

from pydantic import Field

from app.schemas.base import Input

LimitTarget = Literal[
    #: 組織
    "units",
    #: API
    "apis",
]


#: 有効期間上限の設定値
class Lifetime(Input):
    #: トークンの有効期間上限（分）
    max_minutes: int | None = Field(default=None, ge=1, le=60)


#: 利用者に許可するAPI操作
class Permission(Input):
    #: 対象利用者の識別子
    subject: str = Field(min_length=1, max_length=180)
    #: この利用者に許可するAPI操作
    operations: list[str] | None
