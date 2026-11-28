"""unit_lifecycle のAPIで扱う入出力モデルを定義する。"""

from app.schemas.base import Input


#: 組織の移管先
class Transfer(Input):
    #: 移管先の部署またはプロジェクトの識別子
    destination: str
