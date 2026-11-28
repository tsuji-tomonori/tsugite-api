"""ピッキング指示の入出力モデルを定義する。"""

from pydantic import BaseModel


class PickWave(BaseModel):
    wave_id: str
    zone: str
    bin_code: str
    open_lines: int


class PickWaveCount(BaseModel):
    zone: str
    count: int


class PickWaveRange(BaseModel):
    minimum_open_lines: int
    maximum_open_lines: int
