"""配送追跡の入出力モデルを定義する。"""

from pydantic import BaseModel


class Parcel(BaseModel):
    parcel: str
    status: str
    weight_grams: int


class ParcelCount(BaseModel):
    status: str
    count: int


class ParcelTotal(BaseModel):
    total: int
