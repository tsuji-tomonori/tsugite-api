# chat のAPIで扱う入出力モデルを定義する。
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import Input
from app.schemas.catalog import Listing


#: チャットへの質問
class ChatQuestion(Input):
    #: チャットの受付識別子
    job_id: UUID
    #: 質問本文
    question: str = Field(min_length=2, max_length=400)


#: チャットの受付結果
class ChatReceipt(BaseModel):
    #: チャットの受付識別子
    job_id: UUID


#: 操作ガイドの検索結果
class ChatGuide(BaseModel):
    #: ガイドの識別子
    id: str
    #: ガイド名
    title: str
    #: 操作手順
    steps: list[str]
    #: 操作後の状態
    result: str


#: チャットの回答
class ChatResult(BaseModel):
    #: 回答の種類
    kind: Literal[
        #: 回答を作成中
        "pending",
        #: 商品検索
        "catalog",
        #: 操作ガイド
        "manual",
        #: 問い合わせ
        "contact",
        #: 該当なし
        "empty",
        #: 対象外
        "outside",
        #: 処理エラー
        "error",
    ]
    #: 回答本文
    answer: str = ""
    #: おすすめのAPI商品
    products: list[Listing] = Field(default_factory=list)
    #: 該当する操作ガイド
    guides: list[ChatGuide] = Field(default_factory=list)
