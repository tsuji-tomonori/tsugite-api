# inquiries テーブルの列と型を定義する。
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, now


#: 運営への問い合わせ
class Inquiry(Base):
    """問い合わせと回答

    利用者から運営に送信された問い合わせと、管理者からの回答を1件ずつ保存します。
    """

    __tablename__ = "inquiries"

    #: 問い合わせの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 問い合わせを送信した利用者の識別子
    subject: Mapped[str] = mapped_column(String(180))
    #: 問い合わせ本文
    question: Mapped[str] = mapped_column(Text)
    #: 管理者の回答本文
    answer: Mapped[str | None] = mapped_column(Text)
    #: 問い合わせ受付日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 管理者の回答日時
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: 問い合わせ更新時の競合検出番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
