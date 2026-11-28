"""為替レートのHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.exchange_rates import ExchangeRate, ExchangeRateCount, ExchangeRateRange

db = SampleDatabase(
    "CREATE TABLE records (currency TEXT PRIMARY KEY, region TEXT NOT NULL, rate INTEGER NOT NULL)",
    [("JPY", "日本", 1), ("USD", "米国", 150)],
)
app = create_product_app(db, "為替レート", "円換算に使う基準通貨と適用レートを取得します。")


@app.get("/rates", summary="為替レートを一覧で取得")
def list_rates() -> list[ExchangeRate]:
    return db.all("SELECT * FROM records ORDER BY currency")


@app.get(
    "/rates/{currency}",
    summary="為替レートの詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(currency: str) -> ExchangeRate:
    return db.one("SELECT * FROM records WHERE currency = ?", currency)


@app.get("/currency-regions", summary="地域ごとの為替レート件数を集計")
def by_region() -> list[ExchangeRateCount]:
    return db.all("SELECT region, COUNT(*) AS count FROM records GROUP BY region ORDER BY region")


@app.get("/rates-below", summary="円換算レートが上限以下の為替レートを取得")
def below_limit(maximum: int = Query(1, description="円換算レートの上限")) -> list[ExchangeRate]:
    return db.all("SELECT * FROM records WHERE rate <= ? ORDER BY rate, currency", maximum)


@app.get("/rate-range", summary="円換算レートの範囲を取得")
def rate_summary() -> ExchangeRateRange:
    return db.one("SELECT MIN(rate) AS minimum, MAX(rate) AS maximum FROM records")
