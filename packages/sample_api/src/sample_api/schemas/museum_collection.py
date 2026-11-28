"""美術館収蔵品の入出力モデルを定義する。"""

from pydantic import BaseModel


class Exhibit(BaseModel):
    accession: str
    gallery: str
    year: int


class ExhibitCount(BaseModel):
    gallery: str
    count: int


class ExhibitRange(BaseModel):
    minimum: int
    maximum: int
