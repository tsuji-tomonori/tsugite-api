"""keys のAPIで扱う入出力モデルを定義する。"""

from typing import Literal

from pydantic import Field

from app.schemas.base import Input


#: APIキーの発行条件
class KeyInput(Input):
    #: 認証情報の表示名
    name: str = Field(min_length=1, max_length=120)
    #: 利用プロジェクトの識別子
    project: str
    #: APIキーの利用範囲（個人・共有）
    kind: Literal[
        #: 共有
        "shared",
        #: 個人用
        "personal",
    ]
    #: 対象APIの識別子一覧
    api_ids: list[str] = Field(default_factory=list)
