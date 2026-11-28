"""売場補充指示の入出力モデルを定義する。"""

from pydantic import BaseModel


class Refill(BaseModel):
    refill_id: str
    aisle: str
    shelf_label: str
    refill_units: int


class RefillCount(BaseModel):
    aisle: str
    count: int


class RefillRange(BaseModel):
    minimum_refill_units: int
    maximum_refill_units: int
