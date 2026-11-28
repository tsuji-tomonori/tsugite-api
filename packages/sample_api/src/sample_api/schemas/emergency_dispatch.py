"""緊急交換手配の入出力モデルを定義する。"""

from pydantic import BaseModel


class Dispatch(BaseModel):
    dispatch_id: str
    depot: str
    replacement_part: str
    eta_minutes: int


class DispatchCount(BaseModel):
    depot: str
    count: int


class DispatchRange(BaseModel):
    minimum_eta_minutes: int
    maximum_eta_minutes: int
