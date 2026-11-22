import ast
from pathlib import Path

from tests.support.case_text import is_japanese_case_text

ROOT = Path(__file__).resolve().parents[4]


def test_test_cases_have_japanese_descriptions():
    """単体とE2Eのすべてのテスト関数に簡潔な日本語の説明がある。"""
    invalid = []
    total = 0
    for folder in (ROOT / "packages", ROOT / "tests", ROOT / "tools/tests"):
        for path in sorted({*folder.rglob("test_*.py"), *folder.rglob("*_test.py")}):
            if "tests" not in path.relative_to(ROOT).parts:
                continue
            if any(part in {".venv", "dist", "cdk.out", "node_modules"} for part in path.parts):
                continue
            tree = ast.parse(path.read_bytes(), filename=str(path))
            candidates = [*tree.body]
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    candidates.extend(node.body)
            for node in candidates:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name.startswith("test_"):
                    total += 1
                    if not is_japanese_case_text(ast.get_docstring(node) or ""):
                        invalid.append(f"{path.relative_to(ROOT)}:{node.lineno}: {node.name}")
    assert total, "検査対象のテストケースがありません"
    assert not invalid, "簡潔な日本語の説明が必要なテストケース\n" + "\n".join(invalid)
