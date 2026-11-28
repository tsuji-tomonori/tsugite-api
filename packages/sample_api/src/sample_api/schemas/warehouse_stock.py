"""倉庫在庫の入出力モデルを定義する。"""

from pydantic import BaseModel


class StockItem(BaseModel):
    sku: str
    stock: int


class StockItemCount(BaseModel):
    warehouse: str
    count: int


class StockItemTotal(BaseModel):
    total: int


class StockList(BaseModel):
    items: list[StockItem]
