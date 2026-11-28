"""access_rights テーブルの列と型を定義する。"""

import json
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


#: API利用申請・利用権
class Access(Base):
    """環境別の利用申請・利用権

    API・利用プロジェクト・環境の組み合わせごとに、申請から承認・取消までの状態を保存します。個人申請では対象利用者も区別します。
    """

    __tablename__ = "access_rights"

    #: 利用権の識別子
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: 申請対象APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 利用プロジェクトの識別子
    project: Mapped[str] = mapped_column(String(64))
    #: 利用を申請した環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 申請した利用者の識別子
    applicant: Mapped[str | None] = mapped_column(String(180))
    #: 個人申請の対象利用者識別子
    subject: Mapped[str | None] = mapped_column(String(180))
    #: 審査・取消の理由
    decision_note: Mapped[str | None] = mapped_column(Text)
    #: 申請時の回答・利用条件・審査履歴（JSON）
    submission: Mapped[str | None] = mapped_column(Text)
    #: 現在の承認担当
    stage: Mapped[str | None] = mapped_column(String(80))

    @property
    def application(self) -> dict[str, Any]:
        return json.loads(self.submission) if self.submission else {}

    #: 利用申請の理由
    reason: Mapped[str] = mapped_column(Text)
    #: 利用申請の審査状態
    status: Mapped[str] = mapped_column(String(16))
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
