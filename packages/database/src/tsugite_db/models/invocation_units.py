from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: API呼び出しと組織の対応
class LogUnit(Base):
    """呼び出しの組織別集計対象

    呼び出し1件をどの組織の利用実績に含めるか、リクエストと組織の組み合わせで保存します。
    """

    __tablename__ = "invocation_units"
    #: 呼び出しのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 利用実績を集計する組織の識別子
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
