"""列車運行の入出力モデルを定義する。"""

from pydantic import BaseModel


class TrainService(BaseModel):
    train_id: str
    line: str
    delay_minutes: int


class TrainServiceCount(BaseModel):
    line: str
    count: int


class TrainServiceRange(BaseModel):
    minimum: int
    maximum: int
