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
    policy: Mapped[str | None] = mapped_column(Text)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


class Access(Base):
    __tablename__ = "access_rights"

    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32))
    project: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    applicant: Mapped[str | None] = mapped_column(String(180))
    subject: Mapped[str | None] = mapped_column(String(180))
    decision_note: Mapped[str | None] = mapped_column(Text)
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


class Member(Base):
    __tablename__ = "portal_members"
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    username: Mapped[str] = mapped_column(String(180))
    project: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    deleted: Mapped[bool] = mapped_column(default=False)


class Notice(Base):
    __tablename__ = "notices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sender: Mapped[str] = mapped_column(String(180))
    project: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)


class NoticeRead(Base):
    __tablename__ = "notice_reads"
    notice_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)


class AccessLog(Base):
    __tablename__ = "invocation_logs"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor: Mapped[str] = mapped_column(String(180))
    owner: Mapped[str] = mapped_column(String(64))
    project: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    key_id: Mapped[str | None] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(16))
    operation: Mapped[str] = mapped_column(Text)
    status: Mapped[int]
    duration_ms: Mapped[int]


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(32))
    project: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    threshold: Mapped[int]
    minutes: Mapped[int]
    stop: Mapped[bool]
    enabled: Mapped[bool]
    window: Mapped[int] = mapped_column(default=-1)
    calls: Mapped[int] = mapped_column(default=0)


class DirectoryTree(Base):
    __tablename__ = "directory_tree"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    units: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


class Affiliation(Base):
    __tablename__ = "affiliations"
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    leader: Mapped[bool]
    active: Mapped[bool]


class PortalKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    digest: Mapped[str] = mapped_column(String(64))
    project: Mapped[str] = mapped_column(String(64))
    creator: Mapped[str] = mapped_column(String(180))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(12))
    scopes: Mapped[str] = mapped_column(Text)
    revoked: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


class LogUnit(Base):
    __tablename__ = "invocation_units"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
