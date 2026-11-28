"""weather_stations 商品のサンプル操作と応答を定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Observation(BaseModel):
    station_id: str
    basin: str
    rain_mm: int


class ObservationCount(BaseModel):
    basin: str
    count: int


class ObservationRange(BaseModel):
    minimum: int
    maximum: int


db = SampleDatabase(
    "CREATE TABLE records (station_id TEXT PRIMARY KEY, basin TEXT NOT NULL, rain_mm INTEGER NOT NULL)",
    [("WX01", "長良川", 18), ("WX02", "木曽川", 2)],
)
app = db.app("降水観測", "降水観測を流域や降水量（mm）で検索します。")


@app.get("/observations", summary="降水観測を一覧で取得")
def list_observations() -> list[Observation]:
    return db.all("SELECT * FROM records ORDER BY station_id")


@app.get(
    "/observations/{station_id}",
    summary="降水観測の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(station_id: str) -> Observation:
    return db.one("SELECT * FROM records WHERE station_id = ?", station_id)


@app.get("/river-basins", summary="流域ごとの降水観測件数を集計")
def by_basin() -> list[ObservationCount]:
    return db.all("SELECT basin, COUNT(*) AS count FROM records GROUP BY basin ORDER BY basin")


@app.get("/dry-stations", summary="降水量（mm）が上限以下の降水観測を取得")
def below_limit(maximum: int = Query(18, description="降水量（mm）の上限")) -> list[Observation]:
    return db.all("SELECT * FROM records WHERE rain_mm <= ? ORDER BY rain_mm, station_id", maximum)


@app.get("/rainfall-range", summary="降水量（mm）の範囲を取得")
def rain_mm_summary() -> ObservationRange:
    return db.one("SELECT MIN(rain_mm) AS minimum, MAX(rain_mm) AS maximum FROM records")
