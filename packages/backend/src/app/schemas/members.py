"""members のAPIで扱う入出力モデルを定義する。"""

from pydantic import Field, model_validator

from app.core.member_profiles import INVITATION_EMAIL
from app.schemas.base import Input
from app.schemas.profile_fields import FullName, ProfileNames


#: ポータル利用者の招待内容
class Invitation(ProfileNames):
    #: 氏名
    full_name: FullName
    #: 招待先メールアドレス
    email: str = Field(pattern=INVITATION_EMAIL, max_length=150)
    #: 招待先プロジェクトの識別子
    project: str

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_invitation(cls, data):
        # 旧クライアントの役割指定を受理し、所属だけを登録する。
        if isinstance(data, dict) and data.get("role") in ("provider", "consumer"):
            return {key: value for key, value in data.items() if key != "role"}
        return data


#: 個人の管理者ロール
class AdminRole(Input):
    #: 管理者権限を持つか
    admin: bool
