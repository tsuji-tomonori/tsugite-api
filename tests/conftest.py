from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import engine
from app.main import create_app

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def portal(monkeypatch,tmp_path):
    monkeypatch.setenv("TSUGITE_DEMO","1")
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+str(tmp_path/"catalog.db"))
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME",raising=False)
    settings.cache_clear()
    engine.cache_clear()
    cfg=Config(str(ROOT/"backend/alembic.ini"))
    command.upgrade(cfg,"head")
    command.upgrade(cfg,"head")
    with TestClient(create_app()) as api:
        yield api
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()

