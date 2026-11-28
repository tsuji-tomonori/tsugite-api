"""発注受付の入出力モデルを定義する。"""

from pydantic import BaseModel, Field


class PurchaseOrder(BaseModel):
    order_id: str
    supplier: str
    units: int


class PurchaseOrderCount(BaseModel):
    supplier: str
    count: int


class PurchaseOrderTotal(BaseModel):
    total: int


class OrderRequest(BaseModel):
    units: int = Field(gt=0, le=1000)
