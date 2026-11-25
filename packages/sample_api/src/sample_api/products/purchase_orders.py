# purchase_orders 商品のサンプル操作と応答を定義する。
from pydantic import BaseModel, Field

from sample_api.database import SampleDatabase


class PurchaseOrder(BaseModel):
    order_id: str
    supplier: str
    units: int


class PurchaseOrderCount(BaseModel):
    supplier: str
    count: int


class PurchaseOrderTotal(BaseModel):
    total: int


db = SampleDatabase(
    "CREATE TABLE records (order_id TEXT PRIMARY KEY, supplier TEXT NOT NULL, units INTEGER NOT NULL)",
    [("PO-17", "東海商事", 3), ("PO-23", "美濃物流", 18)],
)
app = db.app("発注受付", "購買依頼を送信し、受け付けた注文の番号を取得します。")


@app.get("/orders", summary="発注を一覧で取得")
def list_orders() -> list[PurchaseOrder]:
    return db.all("SELECT * FROM records ORDER BY order_id")


class OrderRequest(BaseModel):
    units: int = Field(gt=0, le=1000)


@app.post("/orders", summary="見本の仕入先で発注結果を試算")
def preview_order(request: OrderRequest) -> PurchaseOrder:
    return db.one(
        "SELECT order_id, supplier, ? AS units FROM records ORDER BY order_id LIMIT 1", request.units
    )


@app.get("/orders/{order_id}", summary="発注の詳細を取得", responses={404: {"description": "該当なし"}})
def detail(order_id: str) -> PurchaseOrder:
    return db.one("SELECT * FROM records WHERE order_id = ?", order_id)


@app.get("/suppliers", summary="仕入先ごとの発注件数を集計")
def by_supplier() -> list[PurchaseOrderCount]:
    return db.all("SELECT supplier, COUNT(*) AS count FROM records GROUP BY supplier ORDER BY supplier")


@app.get("/ordered-units", summary="数量の合計を取得")
def units_summary() -> PurchaseOrderTotal:
    return db.one("SELECT SUM(units) AS total FROM records")
