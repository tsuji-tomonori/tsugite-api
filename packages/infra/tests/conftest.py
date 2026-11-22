from shutil import copyfile

import pytest
from src.infra_app import delivery, stack


@pytest.fixture(autouse=True)
def cdk_test_assets(tmp_path, monkeypatch):
    """単体テスト用の配布物を用意し、アプリのビルドを省けるようにする。"""
    root = tmp_path / "assets"
    for relative in ("build/lambda/handler.py", "packages/frontend/dist/index.html"):
        asset = root / relative
        asset.parent.mkdir(parents=True)
        asset.write_text("test asset\n", encoding="utf-8")
    (root / "build/runtime-layer.zip").write_bytes(b"layer test asset")
    (root / "contracts").mkdir()
    copyfile(stack.ROOT / "contracts/http.toml", root / "contracts/http.toml")
    monkeypatch.setattr(stack, "ROOT", root)
    monkeypatch.setattr(delivery, "ROOT", root)
