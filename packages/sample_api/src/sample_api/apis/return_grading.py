"""返品査定のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.return_grading import Appraisal, AppraisalCount, AppraisalRange

db = SampleDatabase(
    "CREATE TABLE records (return_id TEXT PRIMARY KEY, grade TEXT NOT NULL, "
    "disposition TEXT NOT NULL, resale_yen INTEGER NOT NULL)",
    [("R01", "B級", "整備後再販", 800), ("R02", "A級", "再販可", 2500)],
)
app = create_product_app(db, "返品査定", "返品伝票の査定区分、再販可否の判定、再販価格を照会します。")


@app.get("/appraisals", summary="返品査定を一覧で取得")
def list_appraisals() -> list[Appraisal]:
    return db.all("SELECT * FROM records ORDER BY return_id")


@app.get(
    "/appraisals/{return_id}",
    summary="返品査定の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(return_id: str) -> Appraisal:
    return db.one("SELECT * FROM records WHERE return_id = ?", return_id)


@app.get("/return-grades", summary="返品査定を査定区分別に集計")
def by_grade() -> list[AppraisalCount]:
    return db.all("SELECT grade, COUNT(*) AS count FROM records GROUP BY grade ORDER BY grade")


@app.get("/budget-resales", summary="再販価格が指定値以下の返品査定を取得")
def below_limit(maximum: int = Query(800, description="再販価格の上限")) -> list[Appraisal]:
    return db.all("SELECT * FROM records WHERE resale_yen <= ? ORDER BY resale_yen, return_id", maximum)


@app.get("/resale-prices", summary="再販価格の最小値と最大値を取得")
def resale_yen_summary() -> AppraisalRange:
    return db.one(
        "SELECT MIN(resale_yen) AS minimum_resale_yen, "
        "MAX(resale_yen) AS maximum_resale_yen FROM records"
    )
