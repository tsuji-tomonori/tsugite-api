# ピッキング指示の商品別APIと見本データを定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class PickWave(BaseModel):
    wave_id: str
    zone: str
    bin_code: str
    open_lines: int


class PickWaveCount(BaseModel):
    zone: str
    count: int


class PickWaveRange(BaseModel):
    minimum_open_lines: int
    maximum_open_lines: int


db = SampleDatabase(
    "CREATE TABLE records (wave_id TEXT PRIMARY KEY, zone TEXT NOT NULL, "
    "bin_code TEXT NOT NULL, open_lines INTEGER NOT NULL)",
    [("W01", "冷蔵", "C-03", 2), ("W02", "常温", "A-12", 15)],
)
app = db.app("ピッキング指示", "出荷ウェーブの担当ゾーン、ピック棚番、未完了の行数を照会します。")


@app.get("/waves", summary="ピッキング指示を一覧で取得")
def list_waves() -> list[PickWave]:
    return db.all("SELECT * FROM records ORDER BY wave_id")


@app.get(
    "/waves/{wave_id}",
    summary="ピッキング指示の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(wave_id: str) -> PickWave:
    return db.one("SELECT * FROM records WHERE wave_id = ?", wave_id)


@app.get("/pick-zones", summary="ピッキング指示を担当ゾーン別に集計")
def by_zone() -> list[PickWaveCount]:
    return db.all("SELECT zone, COUNT(*) AS count FROM records GROUP BY zone ORDER BY zone")


@app.get("/short-waves", summary="未完了行数が指定値以下のピッキング指示を取得")
def below_limit(maximum: int = Query(2, description="未完了行数の上限")) -> list[PickWave]:
    return db.all("SELECT * FROM records WHERE open_lines <= ? ORDER BY open_lines, wave_id", maximum)


@app.get("/wave-workloads", summary="未完了行数の最小値と最大値を取得")
def open_lines_summary() -> PickWaveRange:
    return db.one(
        "SELECT MIN(open_lines) AS minimum_open_lines, "
        "MAX(open_lines) AS maximum_open_lines FROM records"
    )
