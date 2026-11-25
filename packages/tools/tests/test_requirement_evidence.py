# 実行予定の単体テストにJUnit結果がなければ、要件を未実行として不合格にする。
import base64
from pathlib import Path
from xml.etree import ElementTree

from packages.tools.testing.requirement_evidence import (
    BROWSER,
    ITEMS,
    Check,
    catalogue,
    read_results,
    render,
)

CASE = "packages/tools/tests/test_example.py::test_policy"
CHECK = Check(CASE, "packages/tools/tests", "")


def test_unexecuted_requirement_fails(tmp_path: Path) -> None:
    """実行予定の単体テストにJUnit結果がなければ、要件を未実行として不合格にする。"""
    assert not render({"配備条件": [CHECK]}, {}, {"packages/tools/tests"}, tmp_path, tmp_path, [])
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "検証未完了　配備条件" in report and "未実行" in (tmp_path / "items/配備条件.md").read_text(
        encoding="utf-8"
    )


def test_skipped_requirement_fails(tmp_path: Path) -> None:
    """同じ要件の一部の条件だけをスキップしても要件を合格にしない。"""
    passed = ElementTree.fromstring('<testcase name="test_policy[ok]"/>')
    skipped = ElementTree.fromstring('<testcase name="test_policy[missing]"><skipped/></testcase>')
    assert not render(
        {"配備条件": [CHECK]},
        {CASE: [passed, skipped]},
        {"packages/tools/tests"},
        tmp_path,
        tmp_path,
        [],
    )
    assert "スキップ" in (tmp_path / "items/配備条件.md").read_text(encoding="utf-8")
    suite = ElementTree.parse(tmp_path / "requirements.xml").getroot()
    assert suite.get("tests") == "1" and suite.get("failures") == "1"


def test_required_browser_capture(tmp_path: Path) -> None:
    """ブラウザーの成功結果には対応する実画像を必要とし、画像を相対リンクから参照できる。"""
    check = Check("tests/e2e/browser/test_ui.py::test_ui", BROWSER, "catalog.png")
    case = ElementTree.fromstring('<testcase name="test_ui"><properties/></testcase>')
    results = {check.node: [case]}
    output = tmp_path / "evidence"
    errors: list[str] = []
    args = ({"商品検索": [check]}, results, {BROWSER}, tmp_path, output, errors)
    assert not render(*args)
    path = "screenshots/ui/catalog.png"
    properties = case.find("properties")
    assert properties is not None
    ElementTree.SubElement(properties, "property", name="screenshot", value=path + "|検索画面")
    assert not render(*args)
    (tmp_path / path).parent.mkdir(parents=True)
    (tmp_path / path).write_bytes(b"\x89PNG\r\n\x1a\n")
    assert not render(*args)
    (tmp_path / path).write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="
        )
    )
    assert render(*args)
    assert (output / path).read_bytes() == (tmp_path / path).read_bytes()
    detail = (output / "items/商品検索.md").read_text(encoding="utf-8")
    assert "![検索画面](../screenshots/ui/catalog.png)" in detail
    assert ElementTree.parse(output / "items/商品検索.xml").find("testcase") is not None
    ElementTree.SubElement(case, "failure", message="期待する候補がありません")
    assert not render(*args)


def test_scope_and_missing_definition(tmp_path: Path) -> None:
    """差分対象外を成功から区別し、テスト未登録の要件と消えた関数を検知する。"""
    items = tmp_path / ITEMS
    items.mkdir(parents=True)
    (items / "要求.md").write_text("# 要求\n", encoding="utf-8")
    _, errors = catalogue(tmp_path, {"packages/tools/tests"})
    assert errors
    source = tmp_path / CASE.partition("::")[0]
    source.parent.mkdir(parents=True)
    source.write_text("def test_old(): pass\n", encoding="utf-8")
    (items / "要求.md").write_text(f"- 受入テスト `{CASE}`\n", encoding="utf-8")
    requirements, errors = catalogue(tmp_path, {"packages/tools/tests"})
    assert errors and not render(requirements, {}, set(), tmp_path, tmp_path, errors)
    source.write_text("def test_policy(): pass\n", encoding="utf-8")
    requirements, errors = catalogue(tmp_path, {"packages/tools/tests"})
    assert not errors and render(requirements, {}, set(), tmp_path, tmp_path, errors)
    assert "対象外　要求" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_junit_errors_survive_reporting(tmp_path: Path) -> None:
    """収集エラーや破損したJUnitがあれば、取得済みの結果を残してCIを失敗させる。"""
    junit = tmp_path / "results.xml"
    junit.write_text(
        f'<testsuite><testcase name="test_policy"><properties><property name="nodeid" value="{CASE}"/>'
        '</properties></testcase><testcase name="collect"><error/></testcase></testsuite>'
    )
    results, errors = read_results([junit, tmp_path / "absent.xml"])
    assert len(results[CASE]) == 1 and len(errors) == 2
    assert not render(
        {"配備条件": [CHECK]}, results, {"packages/tools/tests"}, tmp_path, tmp_path, errors
    )


def test_missing_parameter_result_fails(tmp_path: Path) -> None:
    """収集した条件の一部だけが成功したJUnitでは、実行予定の要件を合格にしない。"""
    case = ElementTree.fromstring(
        '<testcase name="test_policy[a]"><properties>'
        '<property name="variants" value="2"/></properties></testcase>'
    )
    assert not render(
        {"配備条件": [CHECK]}, {CASE: [case]}, {"packages/tools/tests"}, tmp_path, tmp_path, []
    )


def test_evidence_links_verified_requirement(tmp_path, monkeypatch):
    """要件別レポートから検証時点のコミットにある日本語名の原本へ移動できる。"""
    from urllib.parse import unquote

    monkeypatch.setenv("EVIDENCE_COMMIT", "a" * 40)
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/catalog")
    assert render({"配備条件": [CHECK]}, {}, set(), tmp_path, tmp_path, [])
    page = unquote((tmp_path / "items/配備条件.md").read_text())
    assert f"https://github.com/example/catalog/blob/{'a' * 40}/{ITEMS}/配備条件.md" in page
