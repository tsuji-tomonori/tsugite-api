"""画面E2Eをカバレッジ付きで実行する場合だけ、Pyodideの実行行も記録する。"""

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = Path("packages/frontend/src/web_app")
TRACE = ROOT / "tests/support/pyodide_trace.py"
PREFIX = "tsugite-test-coverage "


@pytest.fixture(autouse=True)
def browser_coverage(monkeypatch):
    from coverage import Coverage

    coverage = Coverage.current()
    if coverage is None:
        yield
        return

    from playwright.sync_api import Page

    paths = {path.relative_to(FRONTEND).as_posix(): path.as_posix() for path in FRONTEND.rglob("*.py")}
    tracer = TRACE.read_text(encoding="utf-8")
    pages = set()
    arcs = {}
    original_goto = Page.goto

    def collect(message):
        if message.type == "debug" and message.text.startswith(PREFIX):
            name, batch = json.loads(message.text[len(PREFIX) :])
            arcs.setdefault(paths[name], set()).update(map(tuple, batch))

    def instrument(route):
        response = route.fetch()
        if not response.ok:
            route.fulfill(response=response)
            return
        entry = response.text()
        bootstrap = (
            f"exec({tracer!r}, scope := {{}})\n"
            f"scope['start']({list(paths)!r}, {PREFIX!r})\n"
            f"exec(compile({entry!r}, 'app.py', 'exec'), globals())\n"
        )
        route.fulfill(status=response.status, content_type="text/plain; charset=utf-8", body=bootstrap)

    def goto(page, url, **options):
        if page not in pages and urlsplit(url).hostname == "127.0.0.1":
            page.on("console", collect)
            page.route("**/app.py", instrument)
            pages.add(page)
        return original_goto(page, url, **options)

    monkeypatch.setattr(Page, "goto", goto)
    yield
    if pages and not arcs:
        pytest.fail("ブラウザーで実行した画面コードの行を取得できませんでした")
    if arcs:
        coverage.get_data().add_arcs(arcs)
