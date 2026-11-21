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
    ndjson = (pages / "get-api-access-logs-download.md").read_text()
    assert all(t in ndjson for t in ["application/x-ndjson", "X-Next-Cursor", "Content-Disposition"])


def test_sqlalchemy_and_conditional_aws_writes():
    index = SourceIndex()

    def effects(key):
        return {(kind, name, action) for kind, name, action, *_ in index.trace([key]).effects}

    deleted = effects("app.apis.catalog.register.router.delete")
    assert ("SQL", "assets", "U") in deleted and ("SQL", "assets", "D") not in deleted
    assert ("SQL", "audit_events", "C") in deleted
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
