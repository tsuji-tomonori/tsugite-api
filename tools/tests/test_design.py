import re

from tools.check_text import violations
from tools.design.effects import SourceIndex, raw_sql
from tools.design.generate import SIGNATURE, catalog, generate


def test_all_routes_inputs_outputs_and_cleanup(tmp_path):
    generate(tmp_path)
    files = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.md")}
    _, routes = catalog(True)
    index = (tmp_path / "README.md").read_text()
    for path, method in routes:
        assert f"[{method} `{path}`]" in index
    assert len(re.findall(r"\]\(apis/", index)) == len(routes)
    pages = tmp_path / "apis"
    (pages / "removed.md").write_text(SIGNATURE + "\n")
    (pages / "manual.md").write_text("# 個別メモ\n")
    generate(tmp_path)
    assert not (pages / "removed.md").exists() and (pages / "manual.md").exists()
    assert all((tmp_path / p).read_bytes() == content for p, content in files.items())
    issue = (pages / "post-api-keys.md").read_text()
    assert all(t in issue for t in ["Authorization: Bearer", "KeyInput", "IssuedKey", "201", "422"])
    invoke = (pages / "post-api-invoke-key-environment-project-tail.md").read_text()
    assert all(t in invoke for t in ["X-API-Key", "invocation_logs", "secretsmanager", "lambda", "502"])
    exchange = (pages / "post-api-auth-token.md").read_text()
    assert all(
        t in exchange
        for t in ["client_secret", "Authorization: Bearer", "expires_in", "credential_leases"]
    )
    credential = (pages / "post-api-credentials.md").read_text()
    assert (
        "| api_keys | C | レコードを追加 | db.add |" in credential
        and "| api_keys | U |" not in credential
    )
    rotate = (pages / "post-api-credentials-key_id-rotate.md").read_text()
    assert "| api_keys | U | 秘密値を照合するためのハッシュ値を設定 | digest に代入" in rotate
    ndjson = (pages / "get-api-access-logs-download.md").read_text()
    assert all(t in ndjson for t in ["application/x-ndjson", "X-Next-Cursor", "Content-Disposition"])


def test_sqlalchemy_and_conditional_aws_writes():
    index = SourceIndex()

    def effects(key):
        return {(kind, name, action) for kind, name, action, *_ in index.trace([key]).effects}

    deleted = effects("app.apis.catalog.register.router.delete")
    assert ("SQL", "assets", "U") in deleted and ("SQL", "assets", "D") not in deleted
    assert ("SQL", "audit_events", "C") in deleted
    assert not any(
        table == "assets" and detail in {"status に代入", "decision_note に代入"}
        for _, table, _, _, _, detail in index.trace(["app.apis.catalog.register.router.delete"]).effects
    )
    invite = effects("app.apis.governance.members.invite")
    assert {("AWS", "cognito-idp", "C"), ("AWS", "cognito-idp", "D")} <= invite


def test_sql_sources_relative_import_recursion_and_dynamic_sql(tmp_path):
    module = tmp_path / "example"
    module.mkdir()
    (module / "routes.py").write_text(
        "from .store import read as lookup\ndef route(db):\n    lookup(db)\n"
    )
    (module / "store.py").write_text(
        'from sqlalchemy import text\ndef read(db):\n    db.execute(text("SELECT * FROM inventory"))\n'
        '    db.execute(text(db.info["sql"]))\n    read(db)\n'
    )
    facts = SourceIndex([tmp_path]).trace(["example.routes.route"])
    assert {x[1] for x in facts.effects} == {"inventory"}
    assert {x[0] for x in facts.unresolved} == {"example.store.read"}
    assert set(
        raw_sql("WITH src AS (SELECT id FROM items) INSERT INTO history (id) SELECT id FROM src")
    ) == {("items", "R"), ("history", "C")}
    assert list(raw_sql("DELETE FROM items WHERE id=1")) == [("items", "D")]


def test_text_policy():
    assert not list(violations("設計\n".encode()))
    for invalid in [b"abc", b"abc\n\n", b"abc\r\n", b"\xff\n", b"\xef\xbb\xbftext\n"]:
        assert list(violations(invalid))


def test_business_names_cover_every_operation_field_and_database_column():
    import pytest
    from app.design_names import localize
    from tsugite_db.design_names import design_tables, table_names

    japanese = re.compile(r"[ぁ-んァ-ヶ一-龯]")
    schema, routes = catalog(True)
    for _, operation in routes.values():
        assert japanese.search(operation["summary"])
        for param in operation.get("parameters", []):
            assert japanese.search(param["x-ja-name"]), param["name"]
        for response in operation["responses"].values():
            for key, header in response.get("headers", {}).items():
                assert japanese.search(header["x-ja-name"]), key

    for key, record in schema["components"]["schemas"].items():
        assert japanese.search(record["title"]), key
        for field, definition in record.get("properties", {}).items():
            assert japanese.search(definition["title"]), (key, field)

    names = table_names()
    assert set(names) == {t.name for t, _ in design_tables()}
    for table, _ in design_tables():
        entry = names[table.name]
        for key in ("table", "record", "grain"):
            assert japanese.search(entry[key]), (table.name, key)
        assert set(entry["columns"]) == set(table.columns.keys())
        assert all(japanese.search(name) for name in entry["columns"].values())
    with pytest.raises(ValueError, match="GET /api/new"):
        localize({"paths": {"/api/new": {"get": {}}}}, strict=True)


def test_openapi_preserves_wire_names_and_labels_them_in_context(monkeypatch):
    from app.main import create_app
    from fastapi.testclient import TestClient
    from openapi_spec_validator import validate

    monkeypatch.setenv("TSUGITE_DEMO", "1")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    client = TestClient(create_app())
    schema = client.get("/api/openapi.json").json()
    validate(schema)
    assert client.get("/api/health").json() == {"status": "ok"}
    operation = schema["paths"]["/api/apis/{key}"]["get"]
    assert operation["operationId"] == "detail"
    assert operation["parameters"][0]["x-ja-name"] == "カタログ掲載APIの識別子"
    records = schema["components"]["schemas"]
    for model, expected in (
        ("Health", "サービスの稼働状態"),
        ("Right", "利用申請の審査状態"),
        ("AccessLog", "HTTPステータスコード"),
    ):
        assert records[model]["properties"]["status"]["title"] == expected
    assert records["ReleaseEntry"]["properties"]["removed"]["title"] == "削除した操作・構成要素"
    assert records["Removed"]["properties"]["removed"]["title"] == "所属を解除したか"
