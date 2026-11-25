# business_calendar 商品のサンプル操作と応答を定義する。
from datetime import date

from pydantic import BaseModel

from sample_api.database import SampleDatabase


class BusinessDay(BaseModel):
    business_date: str
    office: str
    hours: int


class BusinessDayCount(BaseModel):
    office: str
    count: int


class BusinessDayTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (business_date TEXT PRIMARY KEY, office TEXT NOT NULL, hours INTEGER NOT NULL)",
    [("2026-11-24", "岐阜", 8), ("2026-11-25", "名古屋", 7)],
)
app = db.app("営業日カレンダー", "次の営業日を照会して、出荷予定日を計算します。")


@app.get("/calendar", summary="営業日を一覧で取得")
def list_calendar() -> list[BusinessDay]:
    return db.all("SELECT * FROM records ORDER BY business_date")


@app.get("/calendar/next", summary="指定日以降で最初の営業日を取得")
def next_day(on_or_after: date = date(2026, 11, 24)) -> BusinessDay:
    return db.one(
        "SELECT * FROM records WHERE business_date >= ? ORDER BY business_date LIMIT 1",
        on_or_after.isoformat(),
    )


@app.get(
    "/calendar/{business_date}",
    summary="営業日の詳細を取得",
    responses={404: {"description": "該当なし"}},
)
def detail(business_date: str) -> BusinessDay:
    return db.one("SELECT * FROM records WHERE business_date = ?", business_date)


@app.get("/offices", summary="事業所ごとの営業日件数を集計")
def by_office() -> list[BusinessDayCount]:
    return db.all("SELECT office, COUNT(*) AS count FROM records GROUP BY office ORDER BY office")


@app.get("/opening-hours", summary="営業時間の合計を取得")
def hours_summary() -> BusinessDayTotal:
    return db.one("SELECT SUM(hours) AS total FROM records")
