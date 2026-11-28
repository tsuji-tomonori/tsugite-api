"""セット構成の入出力モデルを定義する。"""

from pydantic import BaseModel


class Bundle(BaseModel):
    bundle_code: str
    series: str
    component_sku: str
    piece_count: int


class BundleCount(BaseModel):
    series: str
    count: int


class BundleRange(BaseModel):
    minimum_piece_count: int
    maximum_piece_count: int
