# ダッシュボードの再読み込みを検証する。
from __future__ import annotations

import asyncio
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch
from xml.dom.minidom import Document

import pytest
from puepy import Application, Page
from puepy.core import Tag


def test_dashboard_recovers_from_metrics_failure(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """メトリクス取得が失敗しても件数とログを表示し、再読み込みで業務メニューのない利用状況が表示される。"""
    client = portal_module("apis.client")
    js = sys.modules["js"]
    monkeypatch.setattr(js, "document", Document())
    root = js.document.appendChild(js.document.createElement("main"))
    root.setAttribute("id", "app")
    root.setIdAttribute("id")
    js.window.location = SimpleNamespace(hash="#/dashboard")
    js.window.matchMedia = Mock()
    monkeypatch.setitem(sys.modules, "pyodide.ffi.wrappers", SimpleNamespace(add_event_listener=Mock()))
    monkeypatch.setattr(client, "store", Mock())
    source = Path(__file__).resolve().parents[1] / "src/web_app/app.py"
    with patch.object(Application, "mount"), patch.object(asyncio, "ensure_future", lambda c: c.close()):
        portal = runpy.run_path(str(source))
    ctx = portal["ctx"]
    actor = {"admin": True, "owners": []}
    ctx.update(me=actor, home_metrics={"stale": True})
    metrics_available = False

    async def api(path: str) -> dict[str, Any] | list[dict[str, Any]]:
        assert root.inert and root.getAttribute("aria-busy") == "true"
        if path == "/metrics?minutes=60":
            if not metrics_available:
                raise ValueError("集計に失敗しました (500)")
            return {"points": [{"at": "2026-11-22T00:00:00Z", "calls": 2}], "minutes": 60}
        responses: dict[str, dict[str, Any] | list[dict[str, Any]]] = {
            "/me": actor,
            "/notifications/count": {"unread": 0},
            "/dashboard": {"calls": 2, "errors": 0, "inventory": 1, "pending": 0, "approved": 0},
            "/access-logs": [{"status": 200, "method": "GET", "operation": "/stock", "at": "00:00"}],
        }
        return responses[path]

    class DashboardPage(Page):
        def populate(self) -> None:
            portal_module("routing.screen_registry").resolve("dashboard").view()

    def markup() -> str:
        page = DashboardPage()
        with page:
            page.generate_children()
        with patch.object(Tag, "document", Document()):
            return str(page.render().toxml())

    monkeypatch.setattr(client, "api", api)
    with patch.object(Application, "mount"):
        asyncio.run(portal["run"](portal["load"]))
        assert ctx["error"] and "(500)" in ctx["message"]
        assert not root.inert and not root.hasAttribute("aria-busy")
        failed = markup()
        assert "メトリクスを取得できませんでした" in failed and "利用状況を再読み込み" in failed
        assert "管理対象のAPI" in failed and "GET /stock" in failed
        metrics_available = True
        asyncio.run(portal["run"](portal["load"]))
        assert not ctx["error"]
        assert not root.inert and not root.hasAttribute("aria-busy")
        recovered = markup()
        assert "time-chart" in recovered and "利用状況を再読み込み" not in recovered
        assert 'class="chart-scroll"' in recovered and "--buckets:1" in recovered
        assert "業務メニュー" not in recovered
        assert "メトリクスを開く" in recovered and "アクセスログを開く" in recovered
