"""売場補充指示のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.shelf_replenishment import Refill, RefillCount, RefillRange

db = SampleDatabase(
    "CREATE TABLE records (refill_id TEXT PRIMARY KEY, aisle TEXT NOT NULL, "
    "shelf_label TEXT NOT NULL, refill_units INTEGER NOT NULL)",
    [("F01", "日用品", "棚A-2", 6), ("F02", "飲料", "棚B-1", 24)],
)
app = create_product_app(db, "売場補充指示", "売場の陳列棚ごとに補充指示と補充予定数を確認します。")


@app.get("/refills", summary="売場補充指示を一覧で取得")
def list_refills() -> list[Refill]:
    return db.all("SELECT * FROM records ORDER BY refill_id")


@app.get(
    "/refills/{refill_id}",
    summary="売場補充指示の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(refill_id: str) -> Refill:
    return db.one("SELECT * FROM records WHERE refill_id = ?", refill_id)


@app.get("/refill-aisles", summary="売場補充指示を売場別に集計")
def by_aisle() -> list[RefillCount]:
    return db.all("SELECT aisle, COUNT(*) AS count FROM records GROUP BY aisle ORDER BY aisle")


@app.get("/small-refills", summary="補充予定数が指定値以下の売場補充指示を取得")
def below_limit(maximum: int = Query(6, description="補充予定数の上限")) -> list[Refill]:
    return db.all(
        "SELECT * FROM records WHERE refill_units <= ? ORDER BY refill_units, refill_id", maximum
    )


@app.get("/refill-volumes", summary="補充予定数の最小値と最大値を取得")
def refill_units_summary() -> RefillRange:
    return db.one(
        "SELECT MIN(refill_units) AS minimum_refill_units, "
        "MAX(refill_units) AS maximum_refill_units FROM records"
    )
