"""倉庫在庫のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query
from fastapi.responses import JSONResponse

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingStock
from sample_api.schemas.warehouse_stock import StockItem, StockItemCount, StockItemTotal, StockList

db = SampleDatabase(
    "CREATE TABLE records (sku TEXT PRIMARY KEY, warehouse TEXT NOT NULL, stock INTEGER NOT NULL)",
    [("TS-01", "岐阜", 12)],
)
app = create_product_app(db, "倉庫在庫", "SKUごとの在庫数を確認し、棚卸しと引当の差異を調べます。")


@app.get("/items", summary="商品を一覧で取得")
def list_items() -> StockList:
    return {"items": db.all("SELECT sku, stock FROM records ORDER BY sku")}


@app.get(
    "/items/{sku}",
    summary="商品の詳細を取得",
    responses={404: {"model": MissingStock, "description": "該当なし"}},
)
def detail(sku: str) -> StockItem:
    return db.one("SELECT sku, stock FROM records WHERE sku = ?", sku)


@app.get("/warehouses", summary="倉庫ごとの商品件数を集計")
def by_warehouse() -> list[StockItemCount]:
    return db.all(
        "SELECT warehouse, COUNT(*) AS count FROM records GROUP BY warehouse ORDER BY warehouse"
    )


@app.get("/low-stock", summary="在庫数が上限以下の商品を取得")
def below_limit(maximum: int = Query(12, description="在庫数の上限")) -> list[StockItem]:
    return db.all("SELECT sku, stock FROM records WHERE stock <= ? ORDER BY stock, sku", maximum)


@app.get("/stock-total", summary="在庫数の合計を取得")
def stock_summary() -> StockItemTotal:
    return db.one("SELECT SUM(stock) AS total FROM records")


@app.exception_handler(404)
async def missing_item(request, exc):
    return JSONResponse(status_code=404, content={"message": "商品が見つかりません"})
