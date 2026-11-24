from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, now


#: API呼び出し履歴
class AccessLog(Base):
    """API呼び出し記録

    転送APIが記録した1リクエストの呼び出し元、対象、応答結果を保存します。
    """

    __tablename__ = "invocation_logs"
    #: 呼び出しのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: APIの呼び出し日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 呼び出し元の利用者・システム識別子
    actor: Mapped[str] = mapped_column(String(180))
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: 呼び出し元プロジェクトの識別子
    project: Mapped[str] = mapped_column(String(64))
    #: 呼び出したAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 呼び出した環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 利用した認証情報の識別子
    key_id: Mapped[str | None] = mapped_column(String(32))
    #: HTTPメソッド
    method: Mapped[str] = mapped_column(String(16))
    #: 呼び出したAPI操作
    operation: Mapped[str] = mapped_column(Text)
    #: HTTPステータスコード
    status: Mapped[int]
    #: 応答時間（ミリ秒）
    duration_ms: Mapped[int]
    #: 呼び出し時のログ重要度・発生画面・運用作業
    diagnostics: Mapped[str | None] = mapped_column(Text)
