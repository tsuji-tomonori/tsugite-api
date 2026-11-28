# 招待やプロフィール変更時の名前を検証する。
"""Validate profile names consistently at invitation and at later edits."""

from typing import Annotated
from unicodedata import category

from pydantic import Field, field_validator

from app.schemas.base import Input

FullName = Annotated[str, Field(min_length=1, max_length=120)]


#: 利用者の氏名と表示名
class ProfileNames(Input):
    #: 表示名
    display_name: Annotated[str, Field(max_length=80)] | None = None

    @field_validator("full_name", "display_name", mode="before", check_fields=False)
    @classmethod
    def clean_name(cls, value: object) -> object:
        if isinstance(value, str):
            if any(category(char) in {"Cc", "Zl", "Zp"} for char in value):
                raise ValueError("氏名と表示名には改行や制御文字を入力できません")
            return value.strip() or None
        return value
