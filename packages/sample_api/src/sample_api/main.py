"""商品別のFastAPIアプリをベースパスに割り当て、環境ごとのLambdaから呼び出す。"""

from fastapi import FastAPI
from mangum import Mangum

from sample_api.products import (
    bundle_recipes,
    business_calendar,
    count_variances,
    counter_holds,
    emergency_dispatch,
    exchange_rates,
    library_loans,
    meeting_rooms,
    museum_collection,
    packing_cartons,
    parcel_tracking,
    pick_waves,
    power_meters,
    presale_quotas,
    purchase_orders,
    rail_services,
    receipt_inspections,
    return_grading,
    service_intervals,
    shelf_replenishment,
    store_directory,
    warehouse_stock,
    weather_stations,
    web_assortments,
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
        web_assortments,
        bundle_recipes,
        pick_waves,
        presale_quotas,
        receipt_inspections,
        shelf_replenishment,
        service_intervals,
        counter_holds,
        packing_cartons,
        count_variances,
        emergency_dispatch,
        return_grading,
    )
}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
for slug, product in PRODUCTS.items():
    app.mount("/" + slug, product)

# 既存の出品がベースパスなしで呼ぶ在庫照会を維持する。
app.mount("/", warehouse_stock.app)
handler = Mangum(app, lifespan="off")
