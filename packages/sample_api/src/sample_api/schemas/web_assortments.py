"""掲載枠の入出力モデルを定義する。"""

from pydantic import BaseModel


class Listing(BaseModel):
    listing_id: str
    channel: str
    seller_sku: str
    visible_days: int


class ListingCount(BaseModel):
    channel: str
    count: int


class ListingRange(BaseModel):
    minimum_visible_days: int
    maximum_visible_days: int
