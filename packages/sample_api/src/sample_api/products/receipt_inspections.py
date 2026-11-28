"""入荷検品の商品別APIと見本データを定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Inspection(BaseModel):
    inspection_id: str
    dock: str
    lot_code: str
    defect_count: int


class InspectionCount(BaseModel):
    dock: str
    count: int


class InspectionRange(BaseModel):
    minimum_defect_count: int
    maximum_defect_count: int


db = SampleDatabase(
    "CREATE TABLE records (inspection_id TEXT PRIMARY KEY, dock TEXT NOT NULL, "
    "lot_code TEXT NOT NULL, defect_count INTEGER NOT NULL)",
    [("I01", "東荷受口", "L-71", 0), ("I02", "西荷受口", "L-92", 3)],
)
app = db.app("入荷検品", "検品票ごとに検品場所、ロット番号、検出した不良数を照会します。")


@app.get("/inspections", summary="入荷検品を一覧で取得")
def list_inspections() -> list[Inspection]:
    return db.all("SELECT * FROM records ORDER BY inspection_id")


@app.get(
    "/inspections/{inspection_id}",
    summary="入荷検品の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(inspection_id: str) -> Inspection:
    return db.one("SELECT * FROM records WHERE inspection_id = ?", inspection_id)


@app.get("/inspection-docks", summary="入荷検品を荷受口別に集計")
def by_dock() -> list[InspectionCount]:
    return db.all("SELECT dock, COUNT(*) AS count FROM records GROUP BY dock ORDER BY dock")


@app.get("/low-defect-lots", summary="不良数が指定値以下の入荷検品を取得")
def below_limit(maximum: int = Query(0, description="不良数の上限")) -> list[Inspection]:
    return db.all(
        "SELECT * FROM records WHERE defect_count <= ? ORDER BY defect_count, inspection_id", maximum
    )


@app.get("/inspection-defects", summary="不良数の最小値と最大値を取得")
def defect_count_summary() -> InspectionRange:
    return db.one(
        "SELECT MIN(defect_count) AS minimum_defect_count, "
        "MAX(defect_count) AS maximum_defect_count FROM records"
    )
