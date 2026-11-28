"""降水観測の入出力モデルを定義する。"""

from pydantic import BaseModel


class Observation(BaseModel):
    station_id: str
    basin: str
    rain_mm: int


class ObservationCount(BaseModel):
    basin: str
    count: int


class ObservationRange(BaseModel):
    minimum: int
    maximum: int
