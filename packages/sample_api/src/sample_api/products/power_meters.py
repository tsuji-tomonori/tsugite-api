# power_meters 商品のサンプル操作と応答を定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class PowerMeter(BaseModel):
    meter_id: str
    site: str
    kwh: int


class PowerMeterCount(BaseModel):
    site: str
    count: int


class PowerMeterTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (meter_id TEXT PRIMARY KEY, site TEXT NOT NULL, kwh INTEGER NOT NULL)",
    [("M03", "工場", 85), ("M09", "事務所", 20)],
)
app = db.app("電力使用量", "電力計を設置場所や消費電力量（kWh）で検索します。")


@app.get("/meters", summary="電力計を一覧で取得")
def list_meters() -> list[PowerMeter]:
    return db.all("SELECT * FROM records ORDER BY meter_id")


@app.get(
    "/meters/{meter_id}",
    summary="電力計の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(meter_id: str) -> PowerMeter:
    return db.one("SELECT * FROM records WHERE meter_id = ?", meter_id)


@app.get("/meter-sites", summary="設置場所ごとの電力計件数を集計")
def by_site() -> list[PowerMeterCount]:
    return db.all("SELECT site, COUNT(*) AS count FROM records GROUP BY site ORDER BY site")


@app.get("/low-usage", summary="消費電力量（kWh）が上限以下の電力計を取得")
def below_limit(maximum: int = Query(85, description="消費電力量（kWh）の上限")) -> list[PowerMeter]:
    return db.all("SELECT * FROM records WHERE kwh <= ? ORDER BY kwh, meter_id", maximum)


@app.get("/energy-total", summary="消費電力量（kWh）の合計を取得")
def kwh_summary() -> PowerMeterTotal:
    return db.one("SELECT SUM(kwh) AS total FROM records")
