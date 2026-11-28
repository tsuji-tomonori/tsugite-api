"""営業日カレンダーの入出力モデルを定義する。"""

from pydantic import BaseModel


class BusinessDay(BaseModel):
    business_date: str
    office: str
    hours: int


class BusinessDayCount(BaseModel):
    office: str
    count: int


class BusinessDayTotal(BaseModel):
    total: int
