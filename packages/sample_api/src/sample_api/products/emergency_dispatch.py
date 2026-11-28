"""緊急交換手配の商品別APIと見本データを定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Dispatch(BaseModel):
    dispatch_id: str
    depot: str
    replacement_part: str
    eta_minutes: int


class DispatchCount(BaseModel):
    depot: str
    count: int


class DispatchRange(BaseModel):
    minimum_eta_minutes: int
    maximum_eta_minutes: int


db = SampleDatabase(
    "CREATE TABLE records (dispatch_id TEXT PRIMARY KEY, depot TEXT NOT NULL, "
    "replacement_part TEXT NOT NULL, eta_minutes INTEGER NOT NULL)",
    [("D01", "岐阜拠点", "制御基板", 20), ("D02", "高山拠点", "冷却ポンプ", 90)],
)
app = db.app("緊急交換手配", "故障受付ごとに派遣拠点、交換部品、現場到着までの分数を確認します。")


@app.get("/dispatches", summary="緊急交換手配を一覧で取得")
def list_dispatches() -> list[Dispatch]:
    return db.all("SELECT * FROM records ORDER BY dispatch_id")


@app.get(
    "/dispatches/{dispatch_id}",
    summary="緊急交換手配の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(dispatch_id: str) -> Dispatch:
    return db.one("SELECT * FROM records WHERE dispatch_id = ?", dispatch_id)


@app.get("/dispatch-depots", summary="緊急交換手配を派遣拠点別に集計")
def by_depot() -> list[DispatchCount]:
    return db.all("SELECT depot, COUNT(*) AS count FROM records GROUP BY depot ORDER BY depot")


@app.get("/nearby-dispatches", summary="到着予定分数が指定値以下の緊急交換手配を取得")
def below_limit(maximum: int = Query(20, description="到着予定分数の上限")) -> list[Dispatch]:
    return db.all(
        "SELECT * FROM records WHERE eta_minutes <= ? ORDER BY eta_minutes, dispatch_id", maximum
    )


@app.get("/dispatch-times", summary="到着予定分数の最小値と最大値を取得")
def eta_minutes_summary() -> DispatchRange:
    return db.one(
        "SELECT MIN(eta_minutes) AS minimum_eta_minutes, "
        "MAX(eta_minutes) AS maximum_eta_minutes FROM records"
    )
