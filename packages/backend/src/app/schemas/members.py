# members のAPIで扱う入出力モデルを定義する。
from typing import Literal

from pydantic import Field

from app.core.member_profiles import INVITATION_EMAIL
from app.schemas.base import Input
from app.schemas.profile_fields import ProfileNames


#: ポータル利用者の招待内容
class Invitation(ProfileNames):
    #: 招待先メールアドレス
    email: str = Field(pattern=INVITATION_EMAIL, max_length=150)
    #: 招待先プロジェクトの識別子
    project: str
    #: 利用者の役割
    role: Literal[
        #: 利用者
        "consumer",
        #: 提供者
        "provider",
    ]


#: 個人の管理者ロール
class AdminRole(Input):
    #: 管理者権限を持つか
    admin: bool
