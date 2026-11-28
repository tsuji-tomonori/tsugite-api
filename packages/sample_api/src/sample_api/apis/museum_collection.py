"""美術館収蔵品のHTTPエンドポイントと見本データを定義する。"""

from fastapi import Query

from sample_api.core.application import create_product_app
from sample_api.core.database import SampleDatabase
from sample_api.schemas.common import MissingRecord
from sample_api.schemas.museum_collection import Exhibit, ExhibitCount, ExhibitRange

db = SampleDatabase(
    "CREATE TABLE records (accession TEXT PRIMARY KEY, gallery TEXT NOT NULL, year INTEGER NOT NULL)",
    [("A01", "陶芸室", 1880), ("A02", "絵画室", 1930)],
)
app = create_product_app(db, "美術館収蔵品", "収蔵品を展示室や制作年で検索します。")


@app.get("/exhibits", summary="収蔵品を一覧で取得")
def list_exhibits() -> list[Exhibit]:
    return db.all("SELECT * FROM records ORDER BY accession")


@app.get(
    "/exhibits/{accession}",
    summary="収蔵品の詳細を取得",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(accession: str) -> Exhibit:
    return db.one("SELECT * FROM records WHERE accession = ?", accession)


@app.get("/galleries", summary="展示室ごとの収蔵品件数を集計")
def by_gallery() -> list[ExhibitCount]:
    return db.all("SELECT gallery, COUNT(*) AS count FROM records GROUP BY gallery ORDER BY gallery")


@app.get("/early-works", summary="制作年が上限以下の収蔵品を取得")
def below_limit(maximum: int = Query(1880, description="制作年の上限")) -> list[Exhibit]:
    return db.all("SELECT * FROM records WHERE year <= ? ORDER BY year, accession", maximum)


@app.get("/collection-period", summary="制作年の範囲を取得")
def year_summary() -> ExhibitRange:
    return db.one("SELECT MIN(year) AS minimum, MAX(year) AS maximum FROM records")
