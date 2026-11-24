from fastapi import Query
from pydantic import BaseModel

from sample_api.database import SampleDatabase


class TrainService(BaseModel):
    train_id: str
    line: str
    delay_minutes: int


class TrainServiceCount(BaseModel):
    line: str
    count: int


class TrainServiceRange(BaseModel):
    minimum: int
    maximum: int


db = SampleDatabase(
    "CREATE TABLE records (train_id TEXT PRIMARY KEY, line TEXT NOT NULL, delay_minutes INTEGER NOT NULL)",
    [("T12", "本線", 0), ("T24", "支線", 8)],
)
app = db.app("列車運行", "列車を路線や遅延時間（分）で検索します。")


@app.get("/trains", summary="列車を一覧で取得")
def list_trains() -> list[TrainService]:
    return db.all("SELECT * FROM records ORDER BY train_id")


@app.get("/trains/{train_id}", summary="列車の詳細を取得", responses={404: {"description": "該当なし"}})
def detail(train_id: str) -> TrainService:
    return db.one("SELECT * FROM records WHERE train_id = ?", train_id)


@app.get("/rail-lines", summary="路線ごとの列車件数を集計")
def by_line() -> list[TrainServiceCount]:
    return db.all("SELECT line, COUNT(*) AS count FROM records GROUP BY line ORDER BY line")


@app.get("/on-time-services", summary="遅延時間（分）が上限以下の列車を取得")
def below_limit(maximum: int = Query(0, description="遅延時間（分）の上限")) -> list[TrainService]:
    return db.all(
        "SELECT * FROM records WHERE delay_minutes <= ? ORDER BY delay_minutes, train_id", maximum
    )


@app.get("/delay-range", summary="遅延時間（分）の範囲を取得")
def delay_minutes_summary() -> TrainServiceRange:
    return db.one("SELECT MIN(delay_minutes) AS minimum, MAX(delay_minutes) AS maximum FROM records")
