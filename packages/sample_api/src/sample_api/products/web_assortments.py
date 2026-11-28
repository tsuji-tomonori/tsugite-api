# 掲載枠の商品別APIと見本データを定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Listing(BaseModel):
    listing_id: str
    channel: str
    seller_sku: str
    visible_days: int


class ListingCount(BaseModel):
    channel: str
    count: int


class ListingRange(BaseModel):
    minimum_visible_days: int
    maximum_visible_days: int


db = SampleDatabase(
    "CREATE TABLE records (listing_id TEXT PRIMARY KEY, channel TEXT NOT NULL, "
    "seller_sku TEXT NOT NULL, visible_days INTEGER NOT NULL)",
    [("EC01", "自社通販", "TS-01", 2), ("EC02", "モール", "TS-02", 18)],
)
app = db.app("掲載枠", "掲載SKUと販売チャネルごとの公開期間を調べます。")


@app.get("/listings", summary="掲載枠を一覧で取得")
def list_listings() -> list[Listing]:
    return db.all("SELECT * FROM records ORDER BY listing_id")


@app.get(
    "/listings/{listing_id}",
    summary="掲載枠の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(listing_id: str) -> Listing:
    return db.one("SELECT * FROM records WHERE listing_id = ?", listing_id)


@app.get("/listing-channels", summary="掲載枠を販売チャネル別に集計")
def by_channel() -> list[ListingCount]:
    return db.all(
        "SELECT channel, COUNT(*) AS count FROM records "
        "GROUP BY channel ORDER BY channel"
    )


@app.get("/expiring-listings", summary="公開日数が指定値以下の掲載枠を取得")
def below_limit(maximum: int = Query(2, description="公開日数の上限")) -> list[Listing]:
    return db.all(
        "SELECT * FROM records WHERE visible_days <= ? ORDER BY visible_days, listing_id", maximum
    )


@app.get("/listing-periods", summary="公開日数の最小値と最大値を取得")
def visible_days_summary() -> ListingRange:
    return db.one(
        "SELECT MIN(visible_days) AS minimum_visible_days, "
        "MAX(visible_days) AS maximum_visible_days FROM records"
    )
