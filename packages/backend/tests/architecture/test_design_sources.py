"""設計書の入力境界。業務コードはFastAPIの登録情報・構文木・ORMメタデータを通じて参照する。"""

import ast
from importlib.util import resolve_name
from pathlib import Path

from tsugite_db.source_docs import SourceDocs

ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOTS = (ROOT, ROOT / "packages/backend/src", ROOT / "packages/database/src")
ENTRY_POINTS = ("tools.design.generate", "app.design_names", "tsugite_db.design_names")
# These modules supply the running application and ORM objects, both also used outside documentation.
RUNTIME = {"app.main", "tsugite_db.models"}
REGEX = {"re", "regex", "sre_parse", "sre_compile", "_sre"}
READERS = {"open", "read_text", "read_bytes", "get_data", "get_text", "load", "loads", "literal_eval"}


def module_file(module, roots):
    for root in roots:
        base = root.joinpath(*module.split("."))
        for file in (base.with_suffix(".py"), base / "__init__.py"):
            if file.is_file():
                return file
    return None


def local_imports(tree, module, path):
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_name("." * node.level + (node.module or ""), package)
            yield base
            yield from (base + "." + a.name for a in node.names)


def policy_violations(entries, roots):
    pending, visited, errors = list(entries), set(), []
    while pending:
        module = pending.pop()
        if module in visited or module in RUNTIME:
            continue
        visited.add(module)
        path = module_file(module, roots)
        if path is None:
            continue
        tree = ast.parse(path.read_bytes(), filename=str(path))
        for imported in local_imports(tree, module, path):
            if imported.split(".")[0] in REGEX:
                errors.append(f"{module}: 正規表現 {imported}")
            elif module_file(imported, roots):
                pending.append(imported)
        if not any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in tree.body
        ):
            if any(isinstance(n, (ast.Assign, ast.AnnAssign)) for n in tree.body):
                errors.append(f"{module}: 定数だけの外部モジュール")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
            if name in {"__import__", "import_module"}:
                errors.append(f"{module}:{node.lineno}: 動的インポート")
            if name not in READERS:
                continue
            # The only inputs are the checked .py reader and previously generated Markdown for cleanup.
            if module == "tsugite_db.source_docs" and name == "read_text":
                continue
            if (
                module == "tools.design.generate"
                and name == "read_text"
                and isinstance(callee, ast.Attribute)
                and isinstance(callee.value, ast.Name)
                and callee.value.id == "file"
            ):
                continue
            errors.append(f"{module}:{node.lineno}: 外部データの読み込み {name}")
    return errors


def test_design_analysis_uses_only_python_sources_and_syntax_trees():
    """設計解析とその補助モジュールで外部辞書の読み込みと正規表現を検出する。"""
    assert not (violations := policy_violations(ENTRY_POINTS, SOURCE_ROOTS)), violations


def test_design_source_directories_contain_no_sidecar_data():
    """API・ORM・設計書生成のソースに追加された外部マッピングファイルを検出する。"""
    unexpected = []
    for folder in ("packages/backend/src/app", "packages/database/src/tsugite_db", "tools/design"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".py", ".pyi"}:
                unexpected.append(path.relative_to(ROOT))
    assert not unexpected, unexpected


def test_analysis_policy_follows_renamed_helpers_and_relative_imports(tmp_path):
    """別名や相対インポートを経由した正規表現と外部辞書も呼び出し元から検出する。"""
    module = tmp_path / "sample"
    module.mkdir()
    (module / "__init__.py").write_text("")
    (module / "build.py").write_text("from . import helper as h\ndef render(): return h.labels()\n")
    (module / "helper.py").write_text(
        "from re import search as find\nfrom pathlib import Path\n"
        "def labels(): return find('x', Path('renamed.csv').read_text())\n"
    )
    violations = policy_violations(["sample.build"], [tmp_path])
    assert any("正規表現" in message for message in violations)
    assert any("外部データ" in message for message in violations)


def test_schema_field_uses_only_the_comment_on_its_declaration():
    """同名項目の和名を各モデルから取得し、文字列中の偽コメントや通常の注釈を無視する。"""
    source = SourceDocs(
        'sample = """\n#: 偽の和名\n"""\n'
        "class A:\n    #: 稼働状態\n    status: str\n"
        "class B:\n    #: 審査状態\n    status: str\n    # 内部用\n    count: int\n"
    )
    first, second = source.tree.body[1:]
    assert source.fields(first) == {"status": "稼働状態"}
    assert source.fields(second) == {"status": "審査状態", "count": ""}


def test_non_python_source_cannot_supply_business_names(tmp_path):
    """拡張子を変更した外部辞書をコメントの入力として読み込めない。"""
    import pytest
    from tsugite_db.source_docs import read_source

    path = tmp_path / "labels.csv"
    path.write_text("class Replacement: pass\n")
    with pytest.raises(ValueError, match="Pythonソース"):
        read_source(path)
