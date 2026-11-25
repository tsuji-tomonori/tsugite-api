# library_loans 商品のサンプル操作と応答を定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import SampleDatabase


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


db = SampleDatabase(
    "CREATE TABLE records (loan_id TEXT PRIMARY KEY, branch TEXT NOT NULL, days_remaining INTEGER NOT NULL)",
    [("L01", "中央図書館", 2), ("L02", "西分館", 14)],
)
app = db.app("図書貸出", "貸出を図書館や返却までの日数で検索します。")


@app.get("/loans", summary="貸出を一覧で取得")
def list_loans() -> list[Loan]:
    return db.all("SELECT * FROM records ORDER BY loan_id")


@app.get("/loans/{loan_id}", summary="貸出の詳細を取得", responses={404: {"description": "該当なし"}})
def detail(loan_id: str) -> Loan:
    return db.one("SELECT * FROM records WHERE loan_id = ?", loan_id)


@app.get("/library-branches", summary="図書館ごとの貸出件数を集計")
def by_branch() -> list[LoanCount]:
    return db.all("SELECT branch, COUNT(*) AS count FROM records GROUP BY branch ORDER BY branch")


@app.get("/due-soon", summary="返却までの日数が上限以下の貸出を取得")
def below_limit(maximum: int = Query(2, description="返却までの日数の上限")) -> list[Loan]:
    return db.all(
        "SELECT * FROM records WHERE days_remaining <= ? ORDER BY days_remaining, loan_id", maximum
    )


@app.get("/loan-periods", summary="返却までの日数の範囲を取得")
def days_remaining_summary() -> LoanRange:
    return db.one("SELECT MIN(days_remaining) AS minimum, MAX(days_remaining) AS maximum FROM records")
