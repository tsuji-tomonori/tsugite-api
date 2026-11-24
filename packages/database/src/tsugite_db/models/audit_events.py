from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id, now


#: 監査履歴
class Event(Base):
    """監査イベント

    API登録、利用申請、審査、呼び出しなどで記録された操作を1件保存します。
    """

    __tablename__ = "audit_events"

    #: 監査イベントの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 監査対象の操作日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 操作した利用者・システムの識別子
    actor: Mapped[str] = mapped_column(String(180))
    #: 操作の対象となった利用者の識別子
    target_subject: Mapped[str | None] = mapped_column(String(180))
    #: 操作に関係するプロジェクト・組織
    project: Mapped[str] = mapped_column(String(64))
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: 対象APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 操作対象の環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 監査対象の操作種別
    action: Mapped[str] = mapped_column(String(32))
    #: 監査記録の補足内容
    detail: Mapped[str] = mapped_column(Text)
    #: 操作をたどるためのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(40))
