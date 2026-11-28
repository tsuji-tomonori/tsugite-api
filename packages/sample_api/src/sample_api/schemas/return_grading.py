"""返品査定の入出力モデルを定義する。"""

from pydantic import BaseModel


class Appraisal(BaseModel):
    return_id: str
    grade: str
    disposition: str
    resale_yen: int


class AppraisalCount(BaseModel):
    grade: str
    count: int


class AppraisalRange(BaseModel):
    minimum_resale_yen: int
    maximum_resale_yen: int
