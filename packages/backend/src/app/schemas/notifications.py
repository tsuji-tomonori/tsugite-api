"""notifications のAPIで扱う入出力モデルを定義する。"""

from pydantic import Field

from app.schemas.base import Input


#: 送信する通知
class Message(Input):
    #: 通知の件名
    title: str = Field(min_length=1, max_length=160)
    #: 通知本文
    body: str = Field(min_length=1, max_length=3000)
    #: 通知先プロジェクトの識別子
    project: str = Field(min_length=1, max_length=64)
    #: カタログ掲載APIの識別子
    asset_id: str = ""
