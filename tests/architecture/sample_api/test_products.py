# 商品ごとのサンプルAPI実装と公開するOpenAPI仕様の対応を検査する。
from ..core.project import ROOT


def test_each_product_has_a_published_contract():
    """商品ごとに実装モジュールと公開用のOpenAPIファイルが一対一で対応する。"""
    modules = {
        f.stem.replace("_", "-")
        for f in (ROOT / "packages/sample_api/src/sample_api/products").glob("[!_]*.py")
    }
    specs = {p.stem.replace("_", "-") for p in (ROOT / "docs/generated/sample-api").glob("*.yaml")}
    assert modules
    assert modules == specs, modules.symmetric_difference(specs)
