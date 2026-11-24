from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 利用者プロフィール
class MemberProfile(Base):
    """利用者1人のプロフィール

    部署・プロジェクトの所属一覧で表示する利用者の情報を保存します。
    """

    __tablename__ = "portal_member_profiles"
    #: 利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    #: 氏名
    full_name: Mapped[str | None] = mapped_column(String(120))
    #: 表示名
    display_name: Mapped[str | None] = mapped_column(String(80))
    #: 名簿に表示するメールアドレス
    email: Mapped[str | None] = mapped_column(String(320))
    #: メール属性を確認した時刻
    email_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: 同時編集を検知する版番号
    revision: Mapped[int] = mapped_column()

    __mapper_args__ = {"version_id_col": revision}
