from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 組織階層
class DirectoryTree(Base):
    """組織構成の保存記録

    部署とプロジェクトの階層全体を1つの構成として保存します。
    """

    __tablename__ = "directory_tree"
    #: 組織構成の識別子
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    #: 部署・プロジェクトの階層データ（JSON）
    units: Mapped[str] = mapped_column(Text)
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
