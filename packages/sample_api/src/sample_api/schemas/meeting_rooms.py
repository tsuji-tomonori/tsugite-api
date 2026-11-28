"""会議室台帳の入出力モデルを定義する。"""

from pydantic import BaseModel


class MeetingRoom(BaseModel):
    room_id: str
    building: str
    capacity: int


class MeetingRoomCount(BaseModel):
    building: str
    count: int


class MeetingRoomTotal(BaseModel):
    total: int
