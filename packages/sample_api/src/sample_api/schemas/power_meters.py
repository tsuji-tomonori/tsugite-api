"""電力使用量の入出力モデルを定義する。"""

from pydantic import BaseModel


class PowerMeter(BaseModel):
    meter_id: str
    site: str
    kwh: int


class PowerMeterCount(BaseModel):
    site: str
    count: int


class PowerMeterTotal(BaseModel):
    total: int
