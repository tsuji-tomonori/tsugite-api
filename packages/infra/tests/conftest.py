# infra のテストで使う共通フィクスチャを提供する。
from shutil import copyfile

import pytest

from packages.infra.src import stack
from packages.infra.src.components import bindings, chat, delivery


@pytest.fixture(autouse=True)
def cdk_test_assets(tmp_path, monkeypatch):
    """単体テスト用の配布物を用意し、アプリのビルドを省けるようにする。"""
    root = tmp_path / "assets"
    for relative in (
        "build/lambda/handler.py",
        "build/sample-api/sample_api/main.py",
        "build/chat-decision/decision.py",
        "build/chat-llm/completion.py",
        "packages/frontend/dist/index.html",
    ):
        asset = root / relative
        asset.parent.mkdir(parents=True)
        asset.write_text("test asset\n", encoding="utf-8")
    for name in ("runtime", "decision-model", "decision-weights", "model-sdk"):
        (root / "build" / f"{name}-layer.zip").write_bytes(name.encode())
    (root / "deploy/config").mkdir(parents=True)
    copyfile(stack.ROOT / "deploy/config/http.toml", root / "deploy/config/http.toml")
    (root / "packages/model/src").mkdir(parents=True)
    copyfile(
        chat.ROOT / "packages/model/src/manifest.json",
        root / "packages/model/src/manifest.json",
    )
    monkeypatch.setattr(bindings, "ROOT", root)
    monkeypatch.setattr(stack, "ROOT", root)
    monkeypatch.setattr(delivery, "ROOT", root)
    monkeypatch.setattr(chat, "ROOT", root)
