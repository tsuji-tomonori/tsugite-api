"""掲載枠のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.web_assortments import Listing, ListingCount, ListingRange

db = SampleDatabase(
    "CREATE TABLE records (listing_id TEXT PRIMARY KEY, channel TEXT NOT NULL, "
    "seller_sku TEXT NOT NULL, visible_days INTEGER NOT NULL)",
    [("EC01", "自社通販", "TS-01", 2), ("EC02", "モール", "TS-02", 18)],
)
app = create_product_app(db, "掲載枠", "掲載SKUと販売チャネルごとの公開期間を調べます。")


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
    return db.all("SELECT channel, COUNT(*) AS count FROM records GROUP BY channel ORDER BY channel")


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
