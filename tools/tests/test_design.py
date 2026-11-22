import re

from tools.check_text import violations
from tools.design.effects import SourceIndex, raw_sql
from tools.design.generate import SIGNATURE, catalog, generate


def test_all_routes_inputs_outputs_and_cleanup(tmp_path):
    """全APIの入出力を出力し、再生成時に不要な文書を取り除く"""
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


def test_crud_matrices_cover_all_routes_and_match_per_api_evidence(tmp_path):
    """CRUD表の全APIを個別設計書の根拠と照合できる"""
    from tsugite_db.design_names import table_names

    generate(tmp_path)
    document = (tmp_path / "crud.md").read_text()
    sql, aws = document.split("## AWSサービス別の操作表")
    _, routes = catalog(True)
    for section, heading in ((sql, "SQLテーブル"), (aws, "AWSサービス")):
        section = section.split("\n## 静的解析で特定できなかった操作")[0]
        rows = [row.strip("|").split(" | ") for row in section.splitlines() if row.startswith("| ")]
        resources = [re.search(r"`([^`]+)`", cell)[1] for cell in rows[0][1:]]
        used = set()
        seen = set()
        for api, *cells in rows[2:]:
            match = re.search(r"\[(\w+) `([^`]+)`\]\((apis/[^)]+)\)", api)
            method, path, file = match.groups()
            assert (path, method) not in seen
            seen.add((path, method))
            detail = (tmp_path / file).read_text().split(f"### {heading}\n\n")[1].split("\n\n", 1)[0]
            expected = {}
            for row in detail.splitlines()[2:]:
                _, physical, actions, *_ = row.strip(" |").split(" | ")
                expected.setdefault(physical, set()).update(actions.split("/"))
            assert len(cells) == len(resources)
            used.update(expected)
            assert set(expected) <= set(resources)
            for resource, cell in zip(resources, cells, strict=True):
                actions = expected.get(resource, set())
                ordered = [v for v in ("C", "R", "U", "D", "実行", "要確認") if v in actions]
                assert cell.strip() == ("/".join(ordered) or "—"), (path, method, resource)
        assert resources == sorted(table_names() if heading == "SQLテーブル" else used)
        assert seen == set(routes)


def test_sqlalchemy_and_conditional_aws_writes():
    """ORMの操作と条件付きAWS書き込みを設計解析で追跡できる"""
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
    assert effects("app.integrations.spec_archive.archive_spec") == {("AWS", "s3", "C")}
    invite = effects("app.apis.governance.members.invite")
    assert {("AWS", "cognito-idp", "C"), ("AWS", "cognito-idp", "D")} <= invite


def test_sql_sources_relative_import_recursion_and_dynamic_sql(tmp_path):
    """相対インポートと再帰をたどり、動的SQLを識別できる"""
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
    """UTF-8の正常な文書を許可し、異常な符号化や改行を検出する"""
    assert not list(violations("設計\n".encode()))
    for invalid in [b"abc", b"abc\n\n", b"abc\r\n", b"\xff\n", b"\xef\xbb\xbftext\n"]:
        assert list(violations(invalid))


def test_openapi_preserves_wire_names_and_labels_them_in_context(monkeypatch):
    """OpenAPIの通信上の項目名を保ち、用途に応じた和名を表示する"""
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
