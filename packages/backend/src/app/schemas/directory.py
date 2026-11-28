# 部署とプロジェクトの設定・所属変更に使う入力項目を定義する。
from pydantic import Field

from app.schemas.base import Input


#: 部署・プロジェクトの編集内容
class UnitData(Input):
    #: 所属先を分類するメタデータのキー
    kind: str
    #: 部署・プロジェクト名
    name: str = Field(min_length=1, max_length=120)
    #: 親部署の識別子
    parent: str = ""


#: 組織への所属設定
class Membership(Input):
    #: 対象利用者の識別子
    subject: str = Field(min_length=1, max_length=180)
    #: 部署・プロジェクトの識別子
    unit_id: str
    #: 所属先の管理者か
    leader: bool = False
    #: 役職名
    title: str = Field("", max_length=120)


#: 組織の利用停止設定
class State(Input):
    #: 組織の利用を停止中か
    stopped: bool
