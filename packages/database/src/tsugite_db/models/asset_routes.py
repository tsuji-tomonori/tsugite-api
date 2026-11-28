"""asset_routes テーブルの列と型を定義する。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: API呼び出し識別名
class AssetRoute(Base):
    """呼び出し用API識別名

    掲載APIごとに1件を保存し、掲載終了後も再利用を防ぐために保持します。
    """

    __tablename__ = "asset_routes"

    #: 掲載APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 呼び出しURLで使う一意なAPI識別名
    slug: Mapped[str] = mapped_column(String(63), unique=True)
