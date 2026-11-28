"""base のAPIで扱う入出力モデルを定義する。"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def database_time(value: datetime) -> datetime:
    """SQLiteがタイムゾーンを省いた保存時刻にもUTCを付けて返す。"""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


DatabaseTime = Annotated[datetime, AfterValidator(database_time)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
