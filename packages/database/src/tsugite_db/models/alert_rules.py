from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: API呼び出し件数の監視設定
class AlertRule(Base):
    """環境別の呼び出し件数監視ルール

    API・利用プロジェクト・環境ごとに、通知・停止の条件と現在の集計件数を保存します。
    """

    __tablename__ = "alert_rules"
    #: 監視ルールの識別子
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: 監視するAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 監視する利用プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 監視する提供環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 通知・停止の基準件数
    threshold: Mapped[int]
    #: 呼び出し件数の集計区間（分）
    minutes: Mapped[int]
    #: 上限到達後の呼び出しを停止するか
    stop: Mapped[bool]
    #: 監視ルールが有効か
    enabled: Mapped[bool]
    #: 現在の集計区間の番号
    window: Mapped[int] = mapped_column(default=-1)
    #: 現在の集計区間の呼び出し件数
    calls: Mapped[int] = mapped_column(default=0)
