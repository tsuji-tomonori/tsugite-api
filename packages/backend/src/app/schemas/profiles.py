"""profiles のAPIで扱う入出力モデルを定義する。"""

from pydantic import MISSING, Field

from app.schemas.profile_fields import FullName, ProfileNames


#: 利用者プロフィールの編集内容
class ProfileEdit(ProfileNames):
    #: 氏名
    full_name: FullName | MISSING = MISSING
    #: 取得したプロフィールの版番号
    revision: int = Field(ge=0)
