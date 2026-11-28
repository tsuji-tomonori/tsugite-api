"""予約販売枠の入出力モデルを定義する。"""

from pydantic import BaseModel


class Presale(BaseModel):
    presale_id: str
    campaign: str
    release_date: str
    remaining_slots: int


class PresaleCount(BaseModel):
    campaign: str
    count: int


class PresaleRange(BaseModel):
    minimum_remaining_slots: int
    maximum_remaining_slots: int
