# 店頭取り置きの商品別APIと見本データを定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Hold(BaseModel):
    hold_id: str
    counter: str
    pickup_code: str
    days_left: int


class HoldCount(BaseModel):
    counter: str
    count: int


class HoldRange(BaseModel):
    minimum_days_left: int
    maximum_days_left: int


db = SampleDatabase(
    "CREATE TABLE records (hold_id TEXT PRIMARY KEY, counter TEXT NOT NULL, "
    "pickup_code TEXT NOT NULL, days_left INTEGER NOT NULL)",
    [("H01", "北口", "U-31", 1), ("H02", "南口", "U-90", 7)],
)
app = db.app("店頭取り置き", "取り置き伝票の受取窓口、引換番号、保管期限までの残日数を確認します。")


@app.get("/holds", summary="店頭取り置きを一覧で取得")
def list_holds() -> list[Hold]:
    return db.all("SELECT * FROM records ORDER BY hold_id")


@app.get(
    "/holds/{hold_id}",
    summary="店頭取り置きの明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(hold_id: str) -> Hold:
    return db.one("SELECT * FROM records WHERE hold_id = ?", hold_id)


@app.get("/pickup-counters", summary="店頭取り置きを受取窓口別に集計")
def by_counter() -> list[HoldCount]:
    return db.all(
        "SELECT counter, COUNT(*) AS count FROM records "
        "GROUP BY counter ORDER BY counter"
    )


@app.get("/expiring-holds", summary="保管残日数が指定値以下の店頭取り置きを取得")
def below_limit(maximum: int = Query(1, description="保管残日数の上限")) -> list[Hold]:
    return db.all(
        "SELECT * FROM records WHERE days_left <= ? ORDER BY days_left, hold_id", maximum
    )


@app.get("/hold-retention", summary="保管残日数の最小値と最大値を取得")
def days_left_summary() -> HoldRange:
    return db.one(
        "SELECT MIN(days_left) AS minimum_days_left, "
        "MAX(days_left) AS maximum_days_left FROM records"
    )
