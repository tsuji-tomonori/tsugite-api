from typing import Literal

from pydantic import Field

from app.schemas.base import Input


#: APIの公開範囲と承認条件
class Policy(Input):
    #: APIの公開範囲
    visibility: Literal[
        #: 全体公開
        "all",
        #: 限定公開
        "restricted",
    ] = "all"
    #: 閲覧を許可するプロジェクト
    projects: list[str] = Field(default_factory=list)
    #: 閲覧を許可する部署
    departments: list[str] = Field(default_factory=list)
    #: 自動承認の対象部署
    auto_departments: list[str] = Field(default_factory=list)
    #: 自動承認の対象役職
    auto_titles: list[str] = Field(default_factory=list)
    #: 承認を委任する部署
    delegates: list[str] = Field(default_factory=list)
