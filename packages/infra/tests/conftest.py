from shutil import copyfile

import pytest
from src.infra_app import chat, delivery, stack


@pytest.fixture(autouse=True)
def cdk_test_assets(tmp_path, monkeypatch):
    """単体テスト用の配布物を用意し、アプリのビルドを省けるようにする。"""
    root = tmp_path / "assets"
    for relative in (
        "build/lambda/handler.py",
        "build/chat-decision/decision.py",
        "build/chat-llm/completion.py",
        "packages/frontend/dist/index.html",
    ):
        asset = root / relative
        asset.parent.mkdir(parents=True)
        asset.write_text("test asset\n", encoding="utf-8")
    for name in ("runtime", "decision-model", "model-sdk"):
        (root / "build" / f"{name}-layer.zip").write_bytes(name.encode())
    (root / "deploy/config").mkdir(parents=True)
    copyfile(stack.ROOT / "deploy/config/http.toml", root / "deploy/config/http.toml")
    (root / "packages/agent/src/agent/models").mkdir(parents=True)
    copyfile(
        chat.ROOT / "packages/agent/src/agent/models/manifest.json",
        root / "packages/agent/src/agent/models/manifest.json",
    )
    monkeypatch.setattr(stack, "ROOT", root)
    monkeypatch.setattr(delivery, "ROOT", root)
    monkeypatch.setattr(chat, "ROOT", root)
