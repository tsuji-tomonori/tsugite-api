"""梱包箱規格の入出力モデルを定義する。"""

from pydantic import BaseModel


class Carton(BaseModel):
    carton_code: str
    material: str
    size_grade: str
    load_kg: int


class CartonCount(BaseModel):
    material: str
    count: int


class CartonRange(BaseModel):
    minimum_load_kg: int
    maximum_load_kg: int
