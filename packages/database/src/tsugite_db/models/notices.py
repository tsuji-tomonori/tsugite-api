# notices テーブルの列と型を定義する。
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id, now


#: 通知
class Notice(Base):
    """配信通知

    宛先を指定して送信した通知メッセージを1件保存します。
    """

    __tablename__ = "notices"
    #: 通知の識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 通知の送信日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 通知の送信者
    sender: Mapped[str] = mapped_column(String(180))
    #: 通知先プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 通知に関連するAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 通知の件名
    title: Mapped[str] = mapped_column(String(160))
    #: 通知本文
    body: Mapped[str] = mapped_column(Text)
