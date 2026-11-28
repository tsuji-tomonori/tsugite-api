"""全層の単体テスト・アーキテクチャテスト・E2Eに簡潔な日本語の説明がある。"""

import ast

from .case_text import is_japanese_case_text
from .project import ROOT, project_files


def case_functions(path):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    candidates = list(tree.body)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            candidates.extend(node.body)
    for node in candidates:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node


def test_test_cases_have_japanese_descriptions():
    """全層の単体テスト・アーキテクチャテスト・E2Eに簡潔な日本語の説明がある。"""
    invalid = []
    total = 0
    for path in project_files(ROOT, ".py"):
        relative = path.relative_to(ROOT)
        if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        for node in case_functions(path):
            total += 1
            if not is_japanese_case_text(ast.get_docstring(node) or ""):
                invalid.append(f"{relative}:{node.lineno}: {node.name}")
    assert total, "検査対象のテストケースがありません"
    assert not invalid, "簡潔な日本語の説明が必要なテストケース\n" + "\n".join(invalid)
