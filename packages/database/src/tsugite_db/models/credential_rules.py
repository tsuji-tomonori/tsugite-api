# credential_rules テーブルの列と型を定義する。
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 認証情報の利用制限
class CredentialRule(Base):
    """対象別の有効期間・操作制限

    対象のAPI、組織、またはAPIと利用者の組み合わせに対する制限を1件保存します。
    """

    __tablename__ = "credential_rules"
    #: 制限の適用対象を表す識別子
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    #: トークン有効期間の上限（分）
    limit_minutes: Mapped[int | None]
    #: 利用を許可するAPI操作（JSON）
    ops: Mapped[str | None] = mapped_column(Text)
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
