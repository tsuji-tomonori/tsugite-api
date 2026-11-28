"""入荷検品の入出力モデルを定義する。"""

from pydantic import BaseModel


class Inspection(BaseModel):
    inspection_id: str
    dock: str
    lot_code: str
    defect_count: int


class InspectionCount(BaseModel):
    dock: str
    count: int


class InspectionRange(BaseModel):
    minimum_defect_count: int
    maximum_defect_count: int
