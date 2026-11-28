# 棚卸し差異の商品別APIと見本データを定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Variance(BaseModel):
    count_id: str
    sector: str
    reason_code: str
    variance_units: int


class VarianceCount(BaseModel):
    sector: str
    count: int


class VarianceRange(BaseModel):
    minimum_variance_units: int
    maximum_variance_units: int


db = SampleDatabase(
    "CREATE TABLE records (count_id TEXT PRIMARY KEY, sector TEXT NOT NULL, "
    "reason_code TEXT NOT NULL, variance_units INTEGER NOT NULL)",
    [("V01", "第一倉庫", "未計上入荷", 1), ("V02", "第二倉庫", "未計上出荷", 9)],
)
app = db.app("棚卸し差異", "棚卸し票の保管区画、差異理由、帳簿と実棚の差異数を照会します。")


@app.get("/variances", summary="棚卸し差異を一覧で取得")
def list_variances() -> list[Variance]:
    return db.all("SELECT * FROM records ORDER BY count_id")


@app.get(
    "/variances/{count_id}",
    summary="棚卸し差異の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(count_id: str) -> Variance:
    return db.one("SELECT * FROM records WHERE count_id = ?", count_id)


@app.get("/count-sectors", summary="棚卸し差異を保管区画別に集計")
def by_sector() -> list[VarianceCount]:
    return db.all("SELECT sector, COUNT(*) AS count FROM records GROUP BY sector ORDER BY sector")


@app.get("/minor-variances", summary="棚卸差異数が指定値以下の棚卸し差異を取得")
def below_limit(maximum: int = Query(1, description="棚卸差異数の上限")) -> list[Variance]:
    return db.all(
        "SELECT * FROM records WHERE variance_units <= ? ORDER BY variance_units, count_id", maximum
    )


@app.get("/variance-spread", summary="棚卸差異数の最小値と最大値を取得")
def variance_units_summary() -> VarianceRange:
    return db.one(
        "SELECT MIN(variance_units) AS minimum_variance_units, "
        "MAX(variance_units) AS maximum_variance_units FROM records"
    )
