"""店頭取り置きの入出力モデルを定義する。"""

from pydantic import BaseModel


class Hold(BaseModel):
    hold_id: str
    counter: str
    pickup_code: str
    days_left: int


class HoldCount(BaseModel):
    counter: str
    count: int


class HoldRange(BaseModel):
    minimum_days_left: int
    maximum_days_left: int
