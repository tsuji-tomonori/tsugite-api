"""affiliations テーブルの列と型を定義する。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: 利用者の組織所属
class Affiliation(Base):
    """組織別の所属記録

    利用者とメタデータの値の組み合わせごとに、グループ内の役職とリーダー権限を保存します。
    """

    __tablename__ = "affiliations"
    #: 所属する利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    #: 所属先の部署・プロジェクト識別子
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 所属先での役職名
    title: Mapped[str] = mapped_column(String(120))
    #: 所属先の管理権限があるか
    leader: Mapped[bool]
    #: 所属が有効か
    active: Mapped[bool]
