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
    feature = path.parent == Path("portal_pages") and not path.name.startswith("_")
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
            if not isinstance(value, (ast.Tuple, ast.List)) or not value.elts:
                report(definitions[0], "SCREENSにはこの機能が公開する画面を一件以上並べてください")
    elif definitions:
        report(definitions[0], "画面のSCREENSはportal_pagesの機能別モジュールに置いてください")

    for line, imported in dependencies(tree, package):
        target = imported.removeprefix("web_app.")
        parts = target.split(".")
        if len(parts) >= 2 and parts[0] == "portal_pages" and not parts[1].startswith("_"):
            errors.append(
                f"{path}:{line}: 個別画面 {target} の直接参照は画面の自動登録を経由してください"
            )
        if feature and parts[0] in {"app", "portal_shell"}:
            errors.append(f"{path}:{line}: 画面から起動処理・共通レイアウト {target} を参照できません")

    # 画面へのリンクや共通レイアウトの表示条件は許可し、URLごとの描画分岐を検出する。
    if module in {"app", "portal_shell"}:
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
    if module == "portal_navigation":
        names = route_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.IfExp, ast.Match)):
                condition = node.subject if isinstance(node, ast.Match) else node.test
                if uses_route(condition, names) and any(
                    isinstance(item, ast.Await) for item in ast.walk(node)
                ):
                    report(node, "URL別の非同期処理は画面のload_dataに置いてください")
    return errors
