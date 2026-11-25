# 商品に対応するFastAPIアプリを選んでLambdaから呼び出す。
"""商品別のFastAPIをベースパスに取り付け、環境ごとのLambdaで実行する。"""

from fastapi import FastAPI
from mangum import Mangum

from sample_api.products import (
    business_calendar,
    exchange_rates,
    library_loans,
    meeting_rooms,
    museum_collection,
    parcel_tracking,
    power_meters,
    purchase_orders,
    rail_services,
    store_directory,
    warehouse_stock,
    weather_stations,
)

PRODUCTS = {
    module.__name__.rsplit(".", 1)[1].replace("_", "-"): module.app
    for module in (
        warehouse_stock,
        parcel_tracking,
        exchange_rates,
        store_directory,
        purchase_orders,
        business_calendar,
        library_loans,
        weather_stations,
        meeting_rooms,
        rail_services,
        power_meters,
        museum_collection,
    )
}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
for slug, product in PRODUCTS.items():
    app.mount("/" + slug, product)

# 既存の出品がベースパスなしで呼ぶ在庫照会を維持する。
app.mount("/", warehouse_stock.app)
handler = Mangum(app, lifespan="off")
