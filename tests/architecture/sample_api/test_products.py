"""商品別のルート、入出力モデル、公開するOpenAPI仕様の対応を検査する。"""

from ..core.project import ROOT


def test_each_product_has_a_published_contract():
    """商品ごとにルート、入出力モデル、公開用OpenAPIが一対一で対応する。"""
    source = ROOT / "packages/sample_api/src/sample_api"
    routes = {p.stem for p in (source / "apis").glob("[!_]*.py")}
    schemas = {p.stem for p in (source / "schemas").glob("[!_]*.py") if p.stem != "common"}
    contracts = {p.stem.replace("-", "_") for p in (ROOT / "docs/generated/sample-api").glob("*.yaml")}
    assert routes
    assert routes == schemas
    assert routes == contracts
