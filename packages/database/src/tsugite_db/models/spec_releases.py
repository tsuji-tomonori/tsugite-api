# spec_releases テーブルの列と型を定義する。
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, now


#: 商品別API仕様の公開履歴
class SpecRelease(Base):
    """商品API仕様の公開版

    商品ごとに公開したAPI仕様の1版を保存します。商品識別子と公開版番号の組み合わせで1件を特定します。
    """

    __tablename__ = "spec_releases"
    #: 公開した商品の識別子
    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 商品内の公開版番号
    number: Mapped[int] = mapped_column(primary_key=True)
    #: 仕様を公開した日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 保存したOpenAPI文書の内容を識別するハッシュ値
    digest: Mapped[str] = mapped_column(String(64))
    #: 操作・構成要素と内容のハッシュ値の対応（JSON）
    manifest: Mapped[str] = mapped_column(Text)
    #: 公開時の変更内容と版情報（JSON）
    summary: Mapped[str] = mapped_column(Text)
