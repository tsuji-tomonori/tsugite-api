from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .asset_routes import AssetRoute
from .base import Base, new_id


#: APIカタログ
class Asset(Base):
    """掲載API

    提供プロジェクトがカタログに登録したAPIを1件保存します。
    """

    __tablename__ = "assets"

    #: 掲載APIの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    route: Mapped[AssetRoute | None] = relationship(
        primaryjoin="Asset.id == foreign(AssetRoute.asset_id)", lazy="joined"
    )
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: API名
    name: Mapped[str] = mapped_column(String(120))
    #: APIの用途・概要
    summary: Mapped[str] = mapped_column(Text)
    #: 接続先APIの基底パス
    base_path: Mapped[str | None] = mapped_column(String(300))
    #: 登録したOpenAPI仕様（JSON）
    spec: Mapped[str] = mapped_column(Text)
    #: 環境別の申請項目・利用規約・承認経路（JSON）
    offers: Mapped[str | None] = mapped_column(Text)
    #: 次の公開版の変更説明
    release_note: Mapped[str | None] = mapped_column(Text)
    #: 提供環境と接続先の対応（JSON）
    targets: Mapped[str] = mapped_column(Text)
    #: 公開範囲と承認条件（JSON）
    policy: Mapped[str | None] = mapped_column(Text)
    #: カタログから削除した日時
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: カタログで公開中か
    published: Mapped[bool] = mapped_column(default=False)
    #: 管理者による全環境の呼び出し停止
    suspended: Mapped[bool | None] = mapped_column()
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
