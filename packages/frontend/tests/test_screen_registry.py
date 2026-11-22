import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from xml.dom.minidom import Document

import pytest
from puepy.core import Tag

from tools.build_frontend import bundle_styles, copy_app_modules


def test_new_screen_is_packaged_loaded_and_rendered(portal_module, monkeypatch, tmp_path):
    """独立した画面ファイルを追加すると配布物に入り、URLからデータ取得と描画までできる。"""
    source = tmp_path / "source"
    pages = source / "portal_pages"
    pages.mkdir(parents=True)
    (pages / "_sample_text.py").write_text('TITLE = "追加画面"', encoding="utf-8")
    (pages / "sample.py").write_text(
        "from ._sample_text import TITLE\n"
        "from puepy import t\n"
        "from portal_ui import ctx\n"
        "from screen_registry import Screen\n"
        'async def fetch(page):\n    ctx["sample_path"] = page\n'
        'def view():\n    t.p("読み込み済み " + ctx["sample_path"])\n'
        'SCREENS = (Screen("sample", TITLE, view, fetch, group="ヘルプ", order=85),)\n',
        encoding="utf-8",
    )
    (pages / "sample.css").write_text(".sample { color: green; }")
    dist = tmp_path / "dist"
    files = copy_app_modules(source, dist)
    assert files == {
        "/portal_pages/sample.py": "./portal_pages/sample.py",
        "/portal_pages/_sample_text.py": "./portal_pages/_sample_text.py",
    }
    (dist / "ui.css").write_text(".shared { color: blue; }")
    bundle_styles(source, dist)
    css = (dist / "ui.css").read_text()
    assert css.index(".shared") < css.index(".sample")
    package = portal_module("portal_pages")
    monkeypatch.setattr(package, "__path__", [*package.__path__, str(dist / "portal_pages")])
    ui = portal_module("portal_ui")
    user = {"admin": False, "owners": [], "leads": [], "projects": ["finance"]}
    ui.ctx.update(config={"demo": True}, me=user)
    window = portal_module("js").window
    window.location = SimpleNamespace(hash="#/sample")
    window.matchMedia = Mock()
    window.localStorage = Mock()
    api = AsyncMock(side_effect=[user, {"unread": 0}])
    monkeypatch.setattr(portal_module("client"), "api", api)
    asyncio.run(portal_module("portal_navigation").load())
    page = portal_module("portal_shell").Portal()
    with page:
        page.generate_children()
    with patch.object(Tag, "document", Document()):
        dom = page.render()
    assert dom.getElementsByTagName("h1")[0].firstChild.data == "追加画面"
    assert "読み込み済み sample" in dom.toxml()
    assert any(
        button.getAttribute("aria-current") == "page" and button.firstChild.data == "追加画面"
        for button in dom.getElementsByTagName("button")
    )


def test_existing_routes_and_role_menus(portal_module):
    """既存の固定・詳細URLを解決し、役割に応じたメニューを従来の順序で表示する。"""
    registry = portal_module("screen_registry")
    user = {"admin": False, "owners": [], "leads": []}
    menus = registry.menu(user)
    assert [s.path for s in menus["ワークスペース"]] == [
        "home",
        "catalog",
        "keys",
        "mine",
        "notifications",
        "workspace",
        "dashboard",
    ]
    assert [s.path for s in menus["ヘルプ"]] == ["guide", "inquiries"]
    assert [s.path for s in menus["ガバナンス"]] == ["metrics", "logs", "alerts", "audit"]
    assert "管理" not in menus and "提供者メニュー" not in menus
    assert [s.path for s in registry.menu({**user, "leads": ["a"]})["提供者メニュー"]] == ["inbox"]
    menus = registry.menu({**user, "admin": True, "owners": ["a"]})
    assert [s.path for s in menus["管理"]] == ["members"]
    assert [s.path for s in menus["提供者メニュー"]] == ["inventory", "inbox"]
    for path in ("api/stock", "edit/stock", "guide/keys"):
        assert registry.resolve(path).path == path.partition("/")[0] + "/"
    assert registry.resolve("register").parent == "inventory"
    assert registry.resolve("guide/keys").parent == "guide"
    assert registry.resolve("unknown") is None


def test_duplicate_screen_path_is_rejected(portal_module, monkeypatch, tmp_path):
    """別の画面が登録済みのURLを使うと重複したパスを示して失敗する。"""
    (tmp_path / "duplicate.py").write_text(
        'from screen_registry import Screen\nSCREENS = (Screen("catalog", "重複", lambda: None),)\n',
        encoding="utf-8",
    )
    package = portal_module("portal_pages")
    monkeypatch.setattr(package, "__path__", [*package.__path__, str(tmp_path)])
    with pytest.raises(ValueError, match="重複.*catalog"):
        portal_module("screen_registry").screens()
