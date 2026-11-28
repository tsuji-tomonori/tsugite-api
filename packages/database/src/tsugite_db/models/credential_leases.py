"""credential_leases テーブルの列と型を定義する。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 短期トークンの発行状態
class CredentialLease(Base):
    """短期トークンの再利用・更新記録

    発行経路・認証情報・利用者の組み合わせごとに、発行済みトークンを再利用できる期間を記録します。
    """

    __tablename__ = "credential_leases"
    #: 発行経路・認証情報・利用者から作る識別子
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: トークン発行時刻（UNIX秒）
    issued: Mapped[int]
    #: トークン有効期限（UNIX秒）
    expires: Mapped[int]
    #: トークンを更新できる時刻（UNIX秒）
    refresh_at: Mapped[int]
    #: 発行したトークンを区別する一意値
    nonce: Mapped[str] = mapped_column(String(32))
    #: 発行時の認証情報の版番号
    generation: Mapped[int]
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
