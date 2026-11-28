"""portal_members テーブルの列と型を定義する。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: ポータル利用者
class Member(Base):
    """利用者アカウント

    ポータルで管理する利用者1人のアカウント情報を保存します。
    """

    __tablename__ = "portal_members"
    #: 利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    #: ログイン名
    username: Mapped[str] = mapped_column(String(180))
    #: 登録時の所属プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 登録時の役割
    role: Mapped[str] = mapped_column(String(16))
    #: 削除済みか
    deleted: Mapped[bool] = mapped_column(default=False)
