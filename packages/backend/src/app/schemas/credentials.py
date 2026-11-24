from typing import Literal

from pydantic import Field, SecretStr

from app.schemas.base import Input
from app.schemas.keys import KeyInput


#: 認証情報の発行条件
class Issue(KeyInput):
    #: 認証方式
    mode: Literal[
        #: 短期トークン方式
        "bearer",
        #: 利用者を伴うアプリ認証
        "app",
        #: システム間認証
        "system",
    ]
    #: 希望するトークン有効期間（分）
    ttl_minutes: int = Field(60, ge=1, le=60)
    #: 発行から更新可能になるまでの時間（分）
    refresh_minutes: int | None = Field(None, ge=1, le=60)
    #: 対象のAPI操作
    operations: dict[str, list[str]] = Field(default_factory=dict)
    #: 利用を許可する利用者
    users: list[str] = Field(default_factory=list)


#: トークン交換の入力
class Exchange(Input):
    #: クライアント識別子
    client_id: str = Field(min_length=32, max_length=32)
    #: クライアントシークレット
    client_secret: SecretStr
