# members のAPIで扱う入出力モデルを定義する。
from typing import Literal

from pydantic import Field

from app.core.member_profiles import INVITATION_EMAIL
from app.schemas.profile_fields import FullName, ProfileNames


#: ポータル利用者の招待内容
class Invitation(ProfileNames):
    #: 氏名
    full_name: FullName
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
