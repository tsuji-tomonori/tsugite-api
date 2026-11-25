# api_keys テーブルの列と型を定義する。
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_id


#: API認証情報
class PortalKey(Base):
    """発行済みのAPI認証情報

    発行した認証情報ごとに利用範囲、所有者、秘密値の照合情報、失効状態を保存します。
    """

    __tablename__ = "api_keys"
    #: 認証情報の識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 認証方式
    mode: Mapped[str | None] = mapped_column(String(10))
    #: 有効期間・利用者・操作の制限（JSON）
    config: Mapped[str | None] = mapped_column(Text)
    #: 認証情報の発行時刻（UNIX秒）
    created: Mapped[int | None]
    #: 秘密値を照合するためのハッシュ値
    digest: Mapped[str] = mapped_column(String(64))
    #: 認証情報を利用するプロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 認証情報を発行した利用者の識別子
    creator: Mapped[str] = mapped_column(String(180))
    #: 認証情報の表示名
    name: Mapped[str] = mapped_column(String(120))
    #: 認証情報の利用範囲（個人・共有）
    kind: Mapped[str] = mapped_column(String(12))
    #: 利用対象APIの識別子一覧（JSON）
    scopes: Mapped[str] = mapped_column(Text)
    #: 認証情報が失効済みか
    revoked: Mapped[bool] = mapped_column(default=False)
    #: 認証情報の版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
