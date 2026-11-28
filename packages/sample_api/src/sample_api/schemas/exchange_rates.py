"""為替レートの入出力モデルを定義する。"""

from pydantic import BaseModel


class ExchangeRate(BaseModel):
    currency: str
    region: str
    rate: int


class ExchangeRateCount(BaseModel):
    region: str
    count: int


class ExchangeRateRange(BaseModel):
    minimum: int
    maximum: int
