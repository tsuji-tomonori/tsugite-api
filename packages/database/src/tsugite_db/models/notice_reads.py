"""notice_reads テーブルの列と型を定義する。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 通知の既読履歴
class NoticeRead(Base):
    """利用者別の既読記録

    ある利用者がある通知を既読にしたことを1件保存します。
    """

    __tablename__ = "notice_reads"
    #: 既読にした通知の識別子
    notice_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 既読にした利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
