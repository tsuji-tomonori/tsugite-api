"""棚卸し差異の入出力モデルを定義する。"""

from pydantic import BaseModel


class Variance(BaseModel):
    count_id: str
    sector: str
    reason_code: str
    variance_units: int


class VarianceCount(BaseModel):
    sector: str
    count: int


class VarianceRange(BaseModel):
    minimum_variance_units: int
    maximum_variance_units: int
