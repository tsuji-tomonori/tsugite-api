# 予約販売枠の商品別APIと見本データを定義する。
from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class Presale(BaseModel):
    presale_id: str
    campaign: str
    release_date: str
    remaining_slots: int


class PresaleCount(BaseModel):
    campaign: str
    count: int


class PresaleRange(BaseModel):
    minimum_remaining_slots: int
    maximum_remaining_slots: int


db = SampleDatabase(
    "CREATE TABLE records (presale_id TEXT PRIMARY KEY, campaign TEXT NOT NULL, "
    "release_date TEXT NOT NULL, remaining_slots INTEGER NOT NULL)",
    [("P01", "春の先行販売", "2027-03-01", 4), ("P02", "周年予約", "2027-02-01", 80)],
)
app = db.app("予約販売枠", "予約受付を販売キャンペーン別に集計し、残りの受付枠を確認します。")


@app.get("/presales", summary="予約販売枠を一覧で取得")
def list_presales() -> list[Presale]:
    return db.all("SELECT * FROM records ORDER BY presale_id")


@app.get(
    "/presales/{presale_id}",
    summary="予約販売枠の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(presale_id: str) -> Presale:
    return db.one("SELECT * FROM records WHERE presale_id = ?", presale_id)


@app.get("/presale-campaigns", summary="予約販売枠をキャンペーン別に集計")
def by_campaign() -> list[PresaleCount]:
    return db.all("SELECT campaign, COUNT(*) AS count FROM records GROUP BY campaign ORDER BY campaign")


@app.get("/limited-presales", summary="予約可能数が指定値以下の予約販売枠を取得")
def below_limit(maximum: int = Query(4, description="予約可能数の上限")) -> list[Presale]:
    return db.all(
        "SELECT * FROM records WHERE remaining_slots <= ? ORDER BY remaining_slots, presale_id", maximum
    )


@app.get("/presale-capacities", summary="予約可能数の最小値と最大値を取得")
def remaining_slots_summary() -> PresaleRange:
    return db.one(
        "SELECT MIN(remaining_slots) AS minimum_remaining_slots, "
        "MAX(remaining_slots) AS maximum_remaining_slots FROM records"
    )
