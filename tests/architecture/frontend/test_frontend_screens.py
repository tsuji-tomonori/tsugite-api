# 全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。
from pathlib import Path

from ..core.project import ROOT, project_files
from .frontend_screens import screen_violations


def test_portal_screens_keep_their_feature_boundaries():
    """全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。"""
    root = ROOT / "packages/frontend/src/web_app"
    assert any((root / "portal_pages").glob("[!_]*.py")), "検査対象の画面がありません"
    errors = []
    for path in project_files(root, ".py"):
        errors.extend(screen_violations(path.relative_to(root), path.read_text(encoding="utf-8")))
    assert not errors, "\n".join(errors)


def test_feature_can_share_helpers_and_serve_related_routes():
    """一つの機能が補助モジュールを共有し、通常URLと詳細URLを持つ構成を許可する。"""
    source = (
        "from ._filters import apply\n"
        "from portal_ui import ctx\n"
        "from screen_registry import Screen as Page\n"
        "SCREENS = (Page('reports', '一覧', view), Page('reports/', '詳細', detail))\n"
    )
    assert screen_violations(Path("portal_pages/reports.py"), source) == []
    assert screen_violations(Path("portal_pages/_filters.py"), "def apply(): pass") == []


def test_feature_requires_local_screen_declaration():
    """画面定義の欠落、空の宣言、別モジュールからの丸ごと転送を検出する。"""
    path = Path("portal_pages/reports.py")
    for source in ("def view(): pass", "SCREENS = ()", "SCREENS = other.SCREENS"):
        assert any("SCREENS" in error for error in screen_violations(path, source)), source


def test_shared_code_cannot_own_or_import_an_individual_screen():
    """共通コードに移した画面一覧と、別名で取り込んだ個別画面の両方を検出する。"""
    errors = screen_violations(
        Path("screen_registry.py"), "from portal_pages import reports as r\nSCREENS = (r.page,)"
    )
    assert any(":1:" in error and "直接参照" in error for error in errors)
    assert any(":2:" in error and "SCREENS" in error for error in errors)


def test_feature_cannot_depend_on_another_screen_or_the_shell():
    """画面間の相対インポートと共通レイアウトへの逆向き依存を行番号付きで検出する。"""
    errors = screen_violations(
        Path("portal_pages/orders.py"),
        "from .reports import view\nimport portal_shell\nSCREENS = (screen,)\n",
    )
    assert any(":1:" in error and "portal_pages.reports" in error for error in errors)
    assert any(":2:" in error and "portal_shell" in error for error in errors)


def test_shared_layout_delegates_route_dispatch():
    """共通レイアウトへのURL別の条件分岐を検出し、通知やガイドへのリンクを許可する。"""
    path = Path("portal_shell.py")
    assert screen_violations(path, "button(go, 'notifications')") == []
    setup = "from portal_ui import route as current_route\nuser, page = ctx['me'], current_route()\n"
    for source in (
        "if page == 'orders': orders()",
        "view() if route().startswith('orders/') else fallback()",
        "match page:\n    case 'orders': orders()",
    ):
        assert any("振り分け" in error for error in screen_violations(path, setup + source)), source


def test_page_loading_stays_in_the_feature():
    """遷移時の状態破棄を許可し、共通ナビゲーションに戻した画面別API取得を検出する。"""
    path = Path("portal_navigation.py")
    setup = "async def load():\n    page = route()\n"
    cleanup = "    if page != 'keys': ctx.pop('issued_key', None)\n"
    assert screen_violations(path, setup + cleanup) == []
    branch = "    if page == 'orders': await client.api('/orders')\n"
    assert any("load_data" in error for error in screen_violations(path, setup + branch))
