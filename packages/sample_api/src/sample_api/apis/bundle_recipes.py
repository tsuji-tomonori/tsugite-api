"""セット構成のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.bundle_recipes import Bundle, BundleCount, BundleRange
from sample_api.schemas.common import MissingRecord

db = SampleDatabase(
    "CREATE TABLE records (bundle_code TEXT PRIMARY KEY, series TEXT NOT NULL, "
    "component_sku TEXT NOT NULL, piece_count INTEGER NOT NULL)",
    [("B01", "防災", "水ボトル", 3), ("B02", "行楽", "保冷剤", 8)],
)
app = create_product_app(db, "セット構成", "販売セットに含める構成品と同梱点数を確認します。")


@app.get("/bundles", summary="セット構成を一覧で取得")
def list_bundles() -> list[Bundle]:
    return db.all("SELECT * FROM records ORDER BY bundle_code")


@app.get(
    "/bundles/{bundle_code}",
    summary="セット構成の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(bundle_code: str) -> Bundle:
    return db.one("SELECT * FROM records WHERE bundle_code = ?", bundle_code)


@app.get("/bundle-series", summary="セット構成をシリーズ別に集計")
def by_series() -> list[BundleCount]:
    return db.all("SELECT series, COUNT(*) AS count FROM records GROUP BY series ORDER BY series")


@app.get("/compact-bundles", summary="同梱点数が指定値以下のセット構成を取得")
def below_limit(maximum: int = Query(3, description="同梱点数の上限")) -> list[Bundle]:
    return db.all(
        "SELECT * FROM records WHERE piece_count <= ? ORDER BY piece_count, bundle_code", maximum
    )


@app.get("/bundle-sizes", summary="同梱点数の最小値と最大値を取得")
def piece_count_summary() -> BundleRange:
    return db.one(
        "SELECT MIN(piece_count) AS minimum_piece_count, "
        "MAX(piece_count) AS maximum_piece_count FROM records"
    )
