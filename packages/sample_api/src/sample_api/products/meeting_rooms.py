from fastapi import Query
from pydantic import BaseModel

from sample_api.database import SampleDatabase


class MeetingRoom(BaseModel):
    room_id: str
    building: str
    capacity: int


class MeetingRoomCount(BaseModel):
    building: str
    count: int


class MeetingRoomTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (room_id TEXT PRIMARY KEY, building TEXT NOT NULL, capacity INTEGER NOT NULL)",
    [("R101", "北館", 8), ("R202", "南館", 24)],
)
app = db.app("会議室台帳", "会議室を建物や定員で検索します。")


@app.get("/rooms", summary="会議室を一覧で取得")
def list_rooms() -> list[MeetingRoom]:
    return db.all("SELECT * FROM records ORDER BY room_id")


@app.get("/rooms/{room_id}", summary="会議室の詳細を取得", responses={404: {"description": "該当なし"}})
def detail(room_id: str) -> MeetingRoom:
    return db.one("SELECT * FROM records WHERE room_id = ?", room_id)


@app.get("/buildings", summary="建物ごとの会議室件数を集計")
def by_building() -> list[MeetingRoomCount]:
    return db.all("SELECT building, COUNT(*) AS count FROM records GROUP BY building ORDER BY building")


@app.get("/small-rooms", summary="定員が上限以下の会議室を取得")
def below_limit(maximum: int = Query(8, description="定員の上限")) -> list[MeetingRoom]:
    return db.all("SELECT * FROM records WHERE capacity <= ? ORDER BY capacity, room_id", maximum)


@app.get("/room-capacity", summary="定員の合計を取得")
def capacity_summary() -> MeetingRoomTotal:
    return db.one("SELECT SUM(capacity) AS total FROM records")
