"""列車運行のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.rail_services import TrainService, TrainServiceCount, TrainServiceRange

db = SampleDatabase(
    "CREATE TABLE records (train_id TEXT PRIMARY KEY, line TEXT NOT NULL, delay_minutes INTEGER NOT NULL)",
    [("T12", "本線", 0), ("T24", "支線", 8)],
)
app = create_product_app(db, "列車運行", "列車を路線や遅延時間（分）で検索します。")


@app.get("/trains", summary="列車を一覧で取得")
def list_trains() -> list[TrainService]:
    return db.all("SELECT * FROM records ORDER BY train_id")


@app.get(
    "/trains/{train_id}",
    summary="列車の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
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
