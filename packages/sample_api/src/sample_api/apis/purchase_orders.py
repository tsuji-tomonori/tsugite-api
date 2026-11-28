"""発注受付のHTTPエンドポイントと見本データを定義する。"""

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.purchase_orders import (
    OrderRequest,
    PurchaseOrder,
    PurchaseOrderCount,
    PurchaseOrderTotal,
)

db = SampleDatabase(
    "CREATE TABLE records (order_id TEXT PRIMARY KEY, supplier TEXT NOT NULL, units INTEGER NOT NULL)",
    [("PO-17", "東海商事", 3), ("PO-23", "美濃物流", 18)],
)
app = create_product_app(db, "発注受付", "購買依頼を送信し、受け付けた注文の番号を取得します。")


@app.get("/orders", summary="発注を一覧で取得")
def list_orders() -> list[PurchaseOrder]:
    return db.all("SELECT * FROM records ORDER BY order_id")


@app.post("/orders", summary="見本の仕入先で発注結果を試算")
def preview_order(request: OrderRequest) -> PurchaseOrder:
    return db.one(
        "SELECT order_id, supplier, ? AS units FROM records ORDER BY order_id LIMIT 1", request.units
    )


@app.get(
    "/orders/{order_id}",
    summary="発注の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(order_id: str) -> PurchaseOrder:
    return db.one("SELECT * FROM records WHERE order_id = ?", order_id)


@app.get("/suppliers", summary="仕入先ごとの発注件数を集計")
def by_supplier() -> list[PurchaseOrderCount]:
    return db.all("SELECT supplier, COUNT(*) AS count FROM records GROUP BY supplier ORDER BY supplier")


@app.get("/ordered-units", summary="数量の合計を取得")
def units_summary() -> PurchaseOrderTotal:
    return db.one("SELECT SUM(units) AS total FROM records")
