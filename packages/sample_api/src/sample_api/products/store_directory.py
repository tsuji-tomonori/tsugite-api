"""store_directory 商品のサンプル操作と応答を定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Store(BaseModel):
    store_code: str
    city: str
    seats: int


class StoreCount(BaseModel):
    city: str
    count: int


class StoreTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (store_code TEXT PRIMARY KEY, city TEXT NOT NULL, seats INTEGER NOT NULL)",
    [("GF01", "岐阜", 32), ("NG02", "名古屋", 56)],
)
app = db.app("店舗ディレクトリ", "店舗コード、所在地、営業エリアを一覧で取得します。")


@app.get("/stores", summary="店舗を一覧で取得")
def list_stores() -> list[Store]:
    return db.all("SELECT * FROM records ORDER BY store_code")


@app.get(
    "/stores/{store_code}",
    summary="店舗の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(store_code: str) -> Store:
    return db.one("SELECT * FROM records WHERE store_code = ?", store_code)


@app.get("/service-areas", summary="市区町村ごとの店舗件数を集計")
def by_city() -> list[StoreCount]:
    return db.all("SELECT city, COUNT(*) AS count FROM records GROUP BY city ORDER BY city")


@app.get("/small-stores", summary="座席数が上限以下の店舗を取得")
def below_limit(maximum: int = Query(32, description="座席数の上限")) -> list[Store]:
    return db.all("SELECT * FROM records WHERE seats <= ? ORDER BY seats, store_code", maximum)


@app.get("/seat-capacity", summary="座席数の合計を取得")
def seats_summary() -> StoreTotal:
    return db.one("SELECT SUM(seats) AS total FROM records")
