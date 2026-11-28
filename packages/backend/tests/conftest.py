"""backend のテストで使う共通フィクスチャを提供する。"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def contract_cache():
    return {}


@pytest.fixture
def portal(monkeypatch, tmp_path, contract_cache):
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    from tsugite_db.session import engine

    from tests.support.http_contract import Contract

    monkeypatch.setenv("TSUGITE_DEMO", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "catalog.db"))
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    settings.cache_clear()
    engine.cache_clear()
    cfg = Config(str(ROOT / "packages/database/alembic.ini"))
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    with TestClient(create_app()) as api:
        if "portal" not in contract_cache:
            contract_cache["portal"] = Contract(api.app.openapi())
        api.event_hooks["response"].append(contract_cache["portal"].observe)
        yield api
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()
