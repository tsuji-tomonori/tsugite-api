"""設計書の入力境界。業務コードはFastAPIの登録情報・構文木・ORMメタデータを通じて参照する。"""

import ast
from importlib.util import resolve_name

from tsugite_db.source_docs import SourceDocs

from ..core.project import ROOT

SOURCE_ROOTS = (ROOT, *sorted((ROOT / "packages").glob("*/src")))
ENTRY_POINTS = ("packages.tools.design.generate", "app.design_names", "tsugite_db.design_names")
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
        aliases = {
            a.asname or a.name: a.name
            for statement in ast.walk(tree)
            if isinstance(statement, ast.ImportFrom)
            for a in statement.names
        }
        approved_reads = set()
        for function in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            if (module, function.name) == ("tsugite_db.source_docs", "read_source"):
                receiver = "path"
            elif (module, function.name) == ("packages.tools.design.generate", "remove_obsolete_pages"):
                receiver = "file"
            else:
                continue
            approved_reads.update(
                call
                for call in ast.walk(function)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "read_text"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == receiver
            )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
            if isinstance(callee, ast.Name):
                name = aliases.get(name, name)
            if name in {"__import__", "import_module"}:
                errors.append(f"{module}:{node.lineno}: 動的インポート")
            if name not in READERS or node in approved_reads:
                continue
            errors.append(f"{module}:{node.lineno}: 外部データの読み込み {name}")
    return errors


def test_design_analysis_uses_only_python_sources_and_syntax_trees():
    """設計解析とその補助モジュールで外部辞書の読み込みと正規表現を検出する。"""
    assert not (violations := policy_violations(ENTRY_POINTS, SOURCE_ROOTS)), violations


def test_project_tools_do_not_parse_source_files_with_regex():
    """コードやスタイルシートを読む開発ツールで正規表現による解析を検出する。"""
    invalid = []
    for path in (ROOT / "packages/tools").rglob("*.py"):
        if "tests" in path.relative_to(ROOT).parts:
            continue
        tree = ast.parse(path.read_bytes(), filename=str(path))
        imports = set(local_imports(tree, ".".join(path.relative_to(ROOT).with_suffix("").parts), path))
        reads_code = any(
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and n.value.endswith((".py", ".pyi", ".js", ".ts", ".css", ".sql"))
            for n in ast.walk(tree)
        )
        if (reads_code or imports & {"ast", "tokenize", "tinycss2", "sqlglot"}) and imports & REGEX:
            invalid.append(path.relative_to(ROOT))
    assert not invalid, invalid


def test_design_source_directories_contain_no_sidecar_data():
    """廃止した用語集の復活と設計書生成パッケージへの外部辞書の追加を検出する。"""
    removed = (
        "packages/backend/src/app/api_names.toml",
        "packages/database/src/tsugite_db/names.toml",
        "packages/tools/design/labels.py",
    )
    assert not [name for name in removed if (ROOT / name).exists()]
    formats = {".toml", ".json", ".yaml", ".yml", ".csv", ".tsv", ".xml"}
    assert not [p for p in (ROOT / "packages/tools/design").rglob("*") if p.suffix.lower() in formats]


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


def test_business_names_cover_every_operation_field_and_database_column():
    """全API項目とDBカラムに業務用の和名がある"""
    import pytest
    from app.design_names import localize
    from tsugite_db.design_names import design_tables, table_names

    from packages.tools.design.generate import catalog

    def japanese(text):
        return any("ぁ" <= char <= "ヿ" or "一" <= char <= "龯" for char in text)

    schema, routes = catalog(True)
    for _, operation in routes.values():
        assert japanese(operation["summary"])
        for param in operation.get("parameters", []):
            assert japanese(param["x-ja-name"]), param["name"]
        for response in operation["responses"].values():
            for key, header in response.get("headers", {}).items():
                assert japanese(header["x-ja-name"]), key

    for key, record in schema["components"]["schemas"].items():
        assert japanese(record["title"]), key
        for field, definition in record.get("properties", {}).items():
            assert japanese(definition["title"]), (key, field)

    names = table_names()
    assert set(names) == {t.name for t, _ in design_tables()}
    for table, _ in design_tables():
        entry = names[table.name]
        for key in ("table", "record", "grain"):
            assert japanese(entry[key]), (table.name, key)
        assert set(entry["columns"]) == set(table.columns.keys())
        assert all(japanese(name) for name in entry["columns"].values())
    with pytest.raises(ValueError, match="GET /api/new"):
        localize({"paths": {"/api/new": {"get": {}}}}, strict=True)


def test_editing_declaration_comments_changes_openapi_and_design_pages(tmp_path, monkeypatch):
    """定義元のコメントだけを変更するとOpenAPI、API詳細、DB定義書、AWS操作表に反映される。"""
    from app import design_names as api_names
    from tsugite_db import design_names as db_names
    from tsugite_db.source_docs import read_source

    from packages.tools.design import generate as design

    changes = (
        ("packages/backend/src/app/main.py", "サービスの稼働状態を確認する", "稼働確認の試験操作"),
        ("packages/backend/src/app/schemas/outputs.py", "サービスの稼働状態", "稼働確認の試験項目"),
        ("packages/database/src/tsugite_db/models/assets.py", "APIカタログ", "試験用カタログ"),
        (
            "packages/backend/src/app/integrations/spec_archive.py",
            "API仕様文書の保管（Amazon S3） / API仕様文書を保存",
            "試験用保管サービス / 試験用仕様の保存",
        ),
    )
    copies = {}
    for relative, before, after in changes:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        marker = "#: " + before + "\n"
        assert marker in original
        copy = tmp_path / path.name
        copy.write_text(original.replace(marker, "#: " + after + "\n"), encoding="utf-8")
        copies[path] = copy

    def from_copy(path):
        return read_source(copies.get(path.resolve(), path))

    try:
        with monkeypatch.context() as context:
            for module in (api_names, db_names, design):
                context.setattr(module, "read_source", from_copy)
            api_names.declarations.cache_clear()
            api_names.model_fields.cache_clear()
            db_names.table_names.cache_clear()
            spec, _ = design.catalog(True)
            assert spec["paths"]["/api/health"]["get"]["summary"] == "稼働確認の試験操作"
            assert (
                spec["components"]["schemas"]["Health"]["properties"]["status"]["title"]
                == "稼働確認の試験項目"
            )
            output = tmp_path / "generated"
            design.generate(output)
            assert "稼働確認の試験項目" in (output / "apis/get-api-health.md").read_text(
                encoding="utf-8"
            )
            assert "試験用カタログ" in (output / "db/database.md").read_text(encoding="utf-8")
            assert "試験用保管サービス" in (output / "db/crud.md").read_text(encoding="utf-8")
    finally:
        api_names.declarations.cache_clear()
        api_names.model_fields.cache_clear()
        db_names.table_names.cache_clear()
