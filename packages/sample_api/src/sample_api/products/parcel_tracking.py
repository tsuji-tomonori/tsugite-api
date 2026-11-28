"""parcel_tracking 商品のサンプル操作と応答を定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Parcel(BaseModel):
    parcel: str
    status: str
    weight_grams: int


class ParcelCount(BaseModel):
    status: str
    count: int


class ParcelTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (parcel TEXT PRIMARY KEY, status TEXT NOT NULL, weight_grams INTEGER NOT NULL)",
    [("JP17", "配送中", 750), ("JP21", "配達済み", 320)],
)
app = db.app("配送追跡", "送り状番号に対応する荷物の配送状況を照会します。")


@app.get("/parcels", summary="荷物を一覧で取得")
def list_parcels() -> list[Parcel]:
    return db.all("SELECT * FROM records ORDER BY parcel")


@app.get(
    "/parcels/{parcel}",
    summary="荷物の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(parcel: str) -> Parcel:
    return db.one("SELECT * FROM records WHERE parcel = ?", parcel)


@app.get("/delivery-statuses", summary="配送状況ごとの荷物件数を集計")
def by_status() -> list[ParcelCount]:
    return db.all("SELECT status, COUNT(*) AS count FROM records GROUP BY status ORDER BY status")


@app.get("/light-parcels", summary="重量（g）が上限以下の荷物を取得")
def below_limit(maximum: int = Query(750, description="重量（g）の上限")) -> list[Parcel]:
    return db.all("SELECT * FROM records WHERE weight_grams <= ? ORDER BY weight_grams, parcel", maximum)


@app.get("/shipment-weight", summary="重量（g）の合計を取得")
def weight_grams_summary() -> ParcelTotal:
    return db.one("SELECT SUM(weight_grams) AS total FROM records")
