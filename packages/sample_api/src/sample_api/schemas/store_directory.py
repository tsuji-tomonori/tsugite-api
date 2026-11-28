"""店舗ディレクトリの入出力モデルを定義する。"""

from pydantic import BaseModel


class Store(BaseModel):
    store_code: str
    city: str
    seats: int


class StoreCount(BaseModel):
    city: str
    count: int


class StoreTotal(BaseModel):
    total: int
