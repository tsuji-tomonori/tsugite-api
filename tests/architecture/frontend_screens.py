"""ポータルの画面定義とモジュール間依存を、ブラウザーを起動せずに検査する。"""

import ast
from collections.abc import Iterator
from pathlib import Path

from .dependencies import dependencies


def route_names(tree: ast.Module) -> set[str]:
    """ルート取得関数の別名と、戻り値を代入するローカル変数を拾う。"""
    names = {"route"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("portal_ui"):
            names.update(alias.asname or alias.name for alias in node.names if alias.name == "route")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name, expr in assigned_values(target, node.value):
                    if (
                        isinstance(expr, ast.Call)
                        and isinstance(expr.func, ast.Name)
                        and expr.func.id in names
                    ):
                        names.add(name)
    return names


def assigned_values(target: ast.expr, value: ast.expr) -> Iterator[tuple[str, ast.expr]]:
    if isinstance(target, ast.Name):
        yield target.id, value
    elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
        for item, expr in zip(target.elts, value.elts):
            yield from assigned_values(item, expr)


def uses_route(condition: ast.expr, names: set[str]) -> bool:
    for term in ast.walk(condition):
        if isinstance(term, ast.Name) and term.id in names:
            return True
        if isinstance(term, ast.Attribute) and term.attr == "route":
            return True
    return False


def screen_violations(path: Path, source: str) -> list[str]:
    tree = ast.parse(source, filename=str(path))
    module = ".".join(path.with_suffix("").parts)
    package = ("web_app." + module).rpartition(".")[0]
    page = path.parts[0] == "pages" and len(path.parts) >= 3
    feature = page and len(path.parts) == 3 and path.name == "__init__.py" and path.parts[1] != "login"
    errors = []

    def report(node: ast.stmt | ast.expr, message: str) -> None:
        errors.append(f"{path}:{node.lineno}: {message}")

    definitions = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "SCREENS" for target in targets):
                definitions.append(node)
    if feature:
        if len(definitions) != 1:
            errors.append(f"{path}: 公開する画面をモジュール直下のSCREENSに一度だけ定義してください")
        else:
            value = definitions[0].value
            if not isinstance(value, (ast.Tuple, ast.List)) or len(value.elts) != 1:
                report(
                    definitions[0], "SCREENSにはこのディレクトリが公開する画面を一件だけ並べてください"
                )
    elif definitions:
        report(definitions[0], "画面のSCREENSはpages直下の画面パッケージに置いてください")

    imports = [(line, target.removeprefix("web_app.")) for line, target in dependencies(tree, package)]
    if path.parent == Path("pages") and path.name != "__init__.py":
        errors.append(f"{path}: 画面ごとにディレクトリを作成してください")
    if feature and not any(target.startswith("components.") for _, target in imports):
        errors.append(f"{path}: 画面はcomponentsの部品で組み立ててください")

    for line, target in imports:
        parts = target.split(".")
        if parts[0] == "pages":
            same_page = page and parts[:2] == list(path.parts[:2])
            discovery = module == "routing.screen_registry" and target == "pages"
            login = module == "runtime.portal_shell" and target == "pages.login.login_page"
            if not (same_page or discovery or login):
                errors.append(f"{path}:{line}: 個別画面 {target} の直接参照は許可されていません")
        if (page or path.parts[0] == "components") and (
            parts[0] == "app" or parts[:2] == ["runtime", "portal_shell"]
        ):
            errors.append(f"{path}:{line}: 画面から起動処理・共通レイアウト {target} を参照できません")
        if page and parts[0] in {"puepy", "js"}:
            errors.append(f"{path}:{line}: 描画とDOM操作はcomponentsで定義してください")
        if path.parts[0] == "components" and parts[:2] == ["routing", "screen_registry"]:
            errors.append(f"{path}:{line}: 画面レジストリの参照はページから渡してください")
        if (page or path.parts[0] == "components") and parts[0] in {"importlib", "pkgutil"}:
            errors.append(f"{path}:{line}: 画面と部品は静的にインポートしてください")
        if path.parts[0] != "apis" and parts[:2] == ["pyodide", "http"]:
            errors.append(f"{path}:{line}: HTTP通信はapisで定義してください")
        if path.parts[0] == "apis" and parts[0] in {
            "actions",
            "runtime",
            "routing",
            "components",
            "puepy",
        }:
            errors.append(f"{path}:{line}: API処理は表示層から独立させてください")

    # 画面へのリンクや共通レイアウトの表示条件は許可し、URLごとの描画分岐を検出する。
    if module in {"app", "runtime.portal_shell"}:
        names = route_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.IfExp)):
                condition = node.test
            elif isinstance(node, ast.Match):
                condition = node.subject
            else:
                continue
            if uses_route(condition, names):
                report(node, "URLによる画面の振り分けは共通ファイルに追加せずScreenで定義してください")
    if module == "routing.portal_navigation":
        names = route_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.IfExp, ast.Match)):
                condition = node.subject if isinstance(node, ast.Match) else node.test
                if uses_route(condition, names) and any(
                    isinstance(item, ast.Await) for item in ast.walk(node)
                ):
                    report(node, "URL別の非同期処理は画面のload_dataに置いてください")
    return errors
