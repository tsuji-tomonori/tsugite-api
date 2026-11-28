"""定期点検計画の入出力モデルを定義する。"""

from pydantic import BaseModel


class ServicePlan(BaseModel):
    plan_id: str
    workshop: str
    part_number: str
    remaining_hours: int


class ServicePlanCount(BaseModel):
    workshop: str
    count: int


class ServicePlanRange(BaseModel):
    minimum_remaining_hours: int
    maximum_remaining_hours: int
