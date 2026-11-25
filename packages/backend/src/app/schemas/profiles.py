# profiles のAPIで扱う入出力モデルを定義する。
from pydantic import Field

from app.schemas.profile_fields import ProfileNames


#: 利用者プロフィールの編集内容
class ProfileEdit(ProfileNames):
    #: 取得したプロフィールの版番号
    revision: int = Field(ge=0)
