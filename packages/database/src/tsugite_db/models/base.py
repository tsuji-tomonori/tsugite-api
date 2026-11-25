# 全テーブルで共用するORM基底クラスを定義する。
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)
