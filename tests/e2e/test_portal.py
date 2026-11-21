"""Run against a fresh, migrated loopback demo database on every test."""

import os

import pytest
from pytest_given import scenario

from tests.catalog_journey import catalog_journey
from tests.portal_server import serve_portal


@pytest.fixture
def demo_url(tmp_path):
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "e2e.db")}
    with serve_portal(env) as url:
        yield url


@scenario("提供者の公開から承認・取消までを画面で操作する", tags=["CAT", "AUTH", "AUDIT"])
def test_user_flow(demo_url):
    catalog_journey(demo_url)
