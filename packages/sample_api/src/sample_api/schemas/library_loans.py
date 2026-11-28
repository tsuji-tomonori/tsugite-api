"""図書貸出の入出力モデルを定義する。"""

from pydantic import BaseModel


class Loan(BaseModel):
    loan_id: str
    branch: str
    days_remaining: int


class LoanCount(BaseModel):
    branch: str
    count: int


class LoanRange(BaseModel):
    minimum: int
    maximum: int
