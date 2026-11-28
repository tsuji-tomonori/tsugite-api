"""全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。"""

import ast
from pathlib import Path

from ..core.case_text import KANA
from ..core.project import ROOT, project_files
from .frontend_screens import screen_violations


def test_portal_screens_keep_their_feature_boundaries():
    """全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。"""
    root = ROOT / "packages/frontend/src/web_app"
    assert any((root / "pages").glob("*/__init__.py")), "検査対象の画面がありません"
    errors = []
    for folder in (root / "pages").iterdir():
        if folder.is_dir() and folder.name != "__pycache__" and not (folder / "__init__.py").is_file():
            errors.append(f"{folder}: 自動登録に必要な __init__.py がありません")
    for path in project_files(root, ".py"):
        errors.extend(screen_violations(path.relative_to(root), path.read_text(encoding="utf-8")))
    assert not errors, "\n".join(errors)


def test_feature_can_compose_components_and_its_own_helpers():
    """画面が同じディレクトリの補助処理と共通の表示部品を組み合わせられる。"""
    source = (
        "from ._filters import apply\n"
        "from components.reports import view\n"
        "from runtime.portal_ui import ctx\n"
        "from routing.screen_registry import Screen as Page\n"
        "SCREENS = (Page('reports', '一覧', view),)\n"
    )
    assert screen_violations(Path("pages/reports/__init__.py"), source) == []
    assert screen_violations(Path("pages/reports/_filters.py"), "def apply(): pass") == []


def test_feature_requires_local_screen_declaration():
    """画面定義の欠落、空の宣言、別モジュールからの丸ごと転送を検出する。"""
    path = Path("pages/reports/__init__.py")
    for source in (
        "def view(): pass",
        "SCREENS = ()",
        "SCREENS = other.SCREENS",
        "SCREENS = (first, second)",
    ):
        assert any("SCREENS" in error for error in screen_violations(path, source)), source


def test_shared_code_cannot_own_or_import_an_individual_screen():
    """共通コードに移した画面一覧と、別名で取り込んだ個別画面の両方を検出する。"""
    errors = screen_violations(
        Path("routing/screen_registry.py"), "from pages import reports as r\nSCREENS = (r.page,)"
    )
    assert any(":1:" in error and "直接参照" in error for error in errors)
    assert any(":2:" in error and "SCREENS" in error for error in errors)


def test_feature_cannot_depend_on_another_screen_or_the_shell():
    """画面間の相対インポートと共通レイアウトへの逆向き依存を行番号付きで検出する。"""
    errors = screen_violations(
        Path("pages/orders/__init__.py"),
        "from ..reports import view\nfrom runtime import portal_shell\nSCREENS = (screen,)\n",
    )
    assert any(":1:" in error and "pages.reports" in error for error in errors)
    assert any(":2:" in error and "portal_shell" in error for error in errors)


def test_shared_layout_delegates_route_dispatch():
    """共通レイアウトへのURL別の条件分岐を検出し、通知やガイドへのリンクを許可する。"""
    path = Path("runtime/portal_shell.py")
    assert screen_violations(path, "button(go, 'notifications')") == []
    setup = (
        "from runtime.portal_ui import route as current_route\nuser, page = ctx['me'], current_route()\n"
    )
    for source in (
        "if page == 'orders': orders()",
        "view() if route().startswith('orders/') else fallback()",
        "match page:\n    case 'orders': orders()",
    ):
        assert any("振り分け" in error for error in screen_violations(path, setup + source)), source


def test_page_loading_stays_in_the_feature():
    """遷移時の状態破棄を許可し、共通ナビゲーションに戻した画面別API取得を検出する。"""
    path = Path("routing/portal_navigation.py")
    setup = "async def load():\n    page = route()\n"
    cleanup = "    if page != 'keys': ctx.pop('issued_key', None)\n"
    assert screen_violations(path, setup + cleanup) == []
    branch = "    if page == 'orders': await client.api('/orders')\n"
    assert any("load_data" in error for error in screen_violations(path, setup + branch))


def test_components_cannot_import_pages_and_pages_cannot_define_widgets() -> None:
    """部品からの画面参照とページ内の独自描画を別名・相対インポートでも検出する。"""
    for source in ("import pages", "from pages.orders import view as draw", "from .. import pages"):
        assert screen_violations(Path("components/panel.py"), source)
    for source in ("from puepy import t as ui", "from js import document as dom", "import puepy.core"):
        errors = screen_violations(Path("pages/orders/fields.py"), source)
        assert any("描画とDOM操作" in error for error in errors)
    errors = screen_violations(Path("components/request.py"), "from pyodide.http import pyfetch")
    assert any("HTTP通信" in error for error in errors)


def test_frontend_source_describes_files_and_public_functions() -> None:
    """フロントのソース先頭行と公開関数の説明が日本語で記述されていることを確認する。"""
    frontend = ROOT / "packages/frontend"
    errors = []
    for folder in ("src", "tests", "typings", "public"):
        for suffix in (".py", ".css", ".html", ".svg"):
            for path in project_files(frontend / folder, suffix):
                errors.extend(description_errors(path, path.read_text(encoding="utf-8")))
    assert not errors, "\n".join(errors)


def test_markup_and_styles_require_a_japanese_comment() -> None:
    """スタイルとマークアップは、各形式のコメントで先頭に日本語の説明を書く。"""
    assert description_errors(Path("style.css"), "/* search */ .item { color: red; }")
    assert not description_errors(Path("style.css"), "/* 検索欄の外観を定める。 */")
    assert not description_errors(Path("index.html"), "<!-- 検索画面を表示する。 -->")


def description_errors(path: Path, source: str) -> list[str]:
    errors = []
    if path.suffix in {".css", ".html", ".svg"}:
        first = source.partition("\n")[0]
        opening, closing = ("/*", "*/") if path.suffix == ".css" else ("<!--", "-->")
        if not (first.startswith(opening) and first.endswith(closing) and KANA.search(first)):
            errors.append(f"{path}: 先頭行に日本語の説明コメントが必要です")
    if path.suffix == ".py" and "src" in path.parts:
        for node in ast.parse(source).body:
            functions = node.body if isinstance(node, ast.ClassDef) else [node]
            for function in functions:
                if isinstance(
                    function, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not function.name.startswith("_"):
                    if not KANA.search(ast.get_docstring(function) or ""):
                        errors.append(
                            f"{path}:{function.lineno}: 公開関数の責務を日本語で記載してください"
                        )
    return errors
