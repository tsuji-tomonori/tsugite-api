# alerts のAPIで扱う入出力モデルを定義する。
from typing import Literal

from pydantic import Field

from app.schemas.base import Input
from app.schemas.catalog import Env


#: 呼び出し件数の監視条件
class Rule(Input):
    #: カタログ掲載APIの識別子
    asset_id: str
    #: 利用プロジェクトの識別子
    project: str
    #: 提供環境
    environment: Env
    #: 通知・停止の判定に使う呼び出し件数
    threshold: int = Field(ge=1, le=100000000)
    #: 呼び出し件数の集計区間（分）
    minutes: Literal[1, 5, 15, 60, 1440]
    #: 上限到達後の呼び出しを停止するか
    stop: bool
    #: 監視ルールが有効か
    enabled: bool = True


#: 呼び出し件数の監視設定と実績
class RuleResult(Rule):
    #: API名
    name: str
    #: 呼び出し件数
    calls: int
