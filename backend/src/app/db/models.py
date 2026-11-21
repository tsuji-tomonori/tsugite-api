from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    base_path: Mapped[str | None] = mapped_column(String(300))
    spec: Mapped[str] = mapped_column(Text)
    targets: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


class Access(Base):
    __tablename__ = "access_rights"

    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32))
    project: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


class Event(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor: Mapped[str] = mapped_column(String(180))
    project: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str] = mapped_column(String(40))
