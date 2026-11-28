"""梱包箱規格のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.packing_cartons import Carton, CartonCount, CartonRange

db = SampleDatabase(
    "CREATE TABLE records (carton_code TEXT PRIMARY KEY, material TEXT NOT NULL, "
    "size_grade TEXT NOT NULL, load_kg INTEGER NOT NULL)",
    [("C01", "段ボール", "S", 3), ("C02", "強化段ボール", "L", 20)],
)
app = create_product_app(db, "梱包箱規格", "梱包箱の材質と寸法区分ごとの最大積載重量を照会します。")


@app.get("/cartons", summary="梱包箱規格を一覧で取得")
def list_cartons() -> list[Carton]:
    return db.all("SELECT * FROM records ORDER BY carton_code")


@app.get(
    "/cartons/{carton_code}",
    summary="梱包箱規格の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(carton_code: str) -> Carton:
    return db.one("SELECT * FROM records WHERE carton_code = ?", carton_code)


@app.get("/carton-materials", summary="梱包箱規格を材質別に集計")
def by_material() -> list[CartonCount]:
    return db.all("SELECT material, COUNT(*) AS count FROM records GROUP BY material ORDER BY material")


@app.get("/light-duty-cartons", summary="耐荷重キログラムが指定値以下の梱包箱規格を取得")
def below_limit(maximum: int = Query(3, description="耐荷重キログラムの上限")) -> list[Carton]:
    return db.all("SELECT * FROM records WHERE load_kg <= ? ORDER BY load_kg, carton_code", maximum)


@app.get("/carton-loads", summary="耐荷重キログラムの最小値と最大値を取得")
def load_kg_summary() -> CartonRange:
    return db.one("SELECT MIN(load_kg) AS minimum_load_kg, MAX(load_kg) AS maximum_load_kg FROM records")
