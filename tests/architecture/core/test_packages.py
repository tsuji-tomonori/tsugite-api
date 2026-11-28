"""パッケージの追加時にもテストの配置、依存の取得先、カバレッジ設定とファイルの説明を検査する。"""

import ast
import tomllib

from .project import ROOT, has_japanese_module_docstring, project_files
from .test_case_descriptions import case_functions


def test_packages_have_collected_tests_and_metadata():
    """全パッケージがuvワークスペースに属し、単体テストと固有のアーキテクチャテストを持つ。"""
    tool = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]
    members = {path for pattern in tool["uv"]["workspace"]["members"] for path in ROOT.glob(pattern)}
    suites = tool["pytest"]["ini_options"]["testpaths"]
    assert "tests/architecture" in suites
    for package in sorted((ROOT / "packages").iterdir()):
        if not package.is_dir() or package.name.startswith((".", "__")):
            continue
        assert package in members, package
        metadata = tomllib.loads((package / "pyproject.toml").read_text())["project"]
        assert all(metadata.get(key) for key in ("name", "version", "requires-python")), package
        suite = package / "tests"
        assert suite.relative_to(ROOT).as_posix() in suites, suite
        for directory in (suite, ROOT / "tests/architecture" / package.name):
            assert any(
                list(case_functions(file))
                for file in project_files(directory, ".py")
                if file.match("test_*.py") or file.match("*_test.py")
            ), f"{directory}: テスト関数がありません"
        for source in project_files(package, ".py"):
            if "tests" in source.relative_to(package).parts:
                continue
            assert any(
                source.is_relative_to(ROOT / root) for root in tool["coverage"]["run"]["source"]
            ), source


def test_workspace_coverage_and_index():
    """全パッケージに適用する行と分岐の下限、およびuvの既定のPyPI取得先を確認する。"""
    tool = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]
    assert tool["coverage"]["run"]["branch"] is True
    limits = tool["tsugite"]["unit-coverage"]
    assert 90 <= limits["line"] <= 100
    assert 85 <= limits["branch"] <= 100
    assert [i["url"].rstrip("/") for i in tool["uv"]["index"] if i.get("default")] == [
        "https://pypi.org/simple"
    ]


def test_python_files_start_with_japanese_purpose():
    """Pythonの実装と型定義の冒頭に、役割を示す日本語のモジュール説明が一つだけある。"""
    invalid = [
        path.relative_to(ROOT)
        for suffix in (".py", ".pyi")
        for path in project_files(ROOT, suffix)
        if not has_japanese_module_docstring(path.read_text(encoding="utf-8"))
    ]
    assert not invalid, invalid


def test_unit_assertions_check_observations():
    """どの単体テストでも定数だけのassertや同一式同士の等価比較を検出する。"""
    invalid = []
    for package in (ROOT / "packages").glob("*/tests"):
        for path in project_files(package, ".py"):
            for node in ast.walk(ast.parse(path.read_bytes())):
                if not isinstance(node, ast.Assert):
                    continue
                expr = node.test
                constant = isinstance(expr, ast.Constant) and bool(expr.value)
                identical = (
                    isinstance(expr, ast.Compare)
                    and len(expr.ops) == 1
                    and isinstance(expr.ops[0], ast.Eq)
                    and ast.dump(expr.left) == ast.dump(expr.comparators[0])
                )
                if constant or identical:
                    invalid.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not invalid, invalid
