"""要件の原本から作る索引と受入証跡を、一時プロジェクトのJUnitで検証する。"""

import json
import sys
from xml.etree import ElementTree

import pytest

from packages.tools.design import requirements
from packages.tools.testing import requirement_evidence

TITLE = "開発者は、設計を更新したとき、結果を確認できる"
SUITE = "packages/tools/tests"
NODE = f"{SUITE}/test_docs.py::test_report"
DOCUMENT = f"""# **開発者**は、**設計**を更新したとき、**結果**を確認できる

## 背景

**開発者**（実装を更新する人）は、**設計**（実装の取り決め）を更新する。

## なぜ必要か

設計と実装が一致することを確認する。

## 決めた方針

**結果**（検証の成否と所要時間）を出力する。

### 受入テスト

- 受入テスト `{NODE}`

## 却下した方針

却下の記録なし
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDENCE_COMMIT", "fixture-source")
    folder = tmp_path / "docs/requirements/items"
    folder.mkdir(parents=True)
    (folder / f"{TITLE}.md").write_text(DOCUMENT)
    (tmp_path / SUITE).mkdir(parents=True)
    (tmp_path / SUITE / "test_docs.py").write_text(
        'def test_report():\n    """設計の検証結果を表示する。"""\n    assert True\n'
    )
    (tmp_path / "pyproject.toml").write_text(f'[tool.pytest.ini_options]\ntestpaths=["{SUITE}"]\n')
    (tmp_path / "artifacts").mkdir()
    return tmp_path


def test_documents_command_generates_linked_indexes(project, monkeypatch):
    """要件コマンドが日本語の要件、定義元、共通用語を二つの索引に反映する。"""
    monkeypatch.setattr(sys, "argv", ["requirements", "--branch", "fix/index"])
    requirements.main()
    out = project / "artifacts/requirements"
    assert TITLE in (out / "index.md").read_text()
    glossary = (out / "glossary.md").read_text()
    assert all(word in glossary for word in ("開発者", "実装の取り決め", "検証の成否と所要時間"))
    assert (out / "items" / f"{TITLE}.md").read_text() == DOCUMENT


def test_documents_command_rejects_malformed_requirements(project, monkeypatch):
    """共通語彙の定義が欠けている要件を索引作成時に不合格とする。"""
    doc = project / "docs/requirements/items" / f"{TITLE}.md"
    doc.write_text(DOCUMENT.replace("**結果**（検証の成否と所要時間）", "実行結果"))
    monkeypatch.setattr(sys, "argv", ["requirements", "--branch", "fix/index"])
    with pytest.raises(SystemExit) as error:
        requirements.main()
    assert error.value.code == 1


@pytest.mark.parametrize(
    ("outcome", "selected", "label", "status", "junit_child"),
    [
        pytest.param(
            "",
            True,
            "合格",
            0,
            None,
            id="passed",
            marks=pytest.mark.case_detail("成功した対象ケースを合格にする"),
        ),
        pytest.param(
            '<failure message="期待値不一致"/>',
            True,
            "不合格",
            1,
            "failure",
            id="failed",
            marks=pytest.mark.case_detail("失敗を要件ページとJUnitに記録する"),
        ),
        pytest.param(
            '<error message="起動失敗"/>',
            True,
            "不合格",
            1,
            "failure",
            id="error",
            marks=pytest.mark.case_detail("テストエラーを不合格として記録する"),
        ),
        pytest.param(
            "<skipped/>",
            True,
            "検証未完了",
            1,
            "failure",
            id="skipped",
            marks=pytest.mark.case_detail("対象テストのスキップで未完了とする"),
        ),
        pytest.param(
            None,
            False,
            "対象外",
            0,
            "skipped",
            id="outside",
            marks=pytest.mark.case_detail("実行計画にない層は対象外とする"),
        ),
    ],
)
def test_requirement_evidence_command(
    project, monkeypatch, outcome, selected, label, status, junit_child
):
    """差分の実行予定とJUnit結果を照合し、要件ページと機械判定用XMLの両方を生成する。"""
    monkeypatch.setattr(sys, "argv", ["evidence", "--check"])
    assert requirement_evidence.main() == 0
    artifacts = project / "artifacts"
    plan = {"suites": [SUITE] if selected else [], "aws": False, "aws_portal_only": False}
    (artifacts / "ci-plan.json").write_text(json.dumps(plan))
    if outcome is not None:
        (artifacts / "junit.xml").write_text(
            f'<testsuite><testcase name="test_report" classname="packages.tools.tests.test_docs" '
            f'file="{SUITE}/test_docs.py" time="0.123"><properties><property name="nodeid" value="{NODE}"/>'
            f'<property name="variants" value="1"/><property name="case_description" value="結果を表示する。"/>'
            f"</properties>{outcome}</testcase></testsuite>"
        )
    monkeypatch.setattr(sys, "argv", ["evidence", "--plan", "artifacts/ci-plan.json"])
    assert requirement_evidence.main() == status
    result = project / "evidence"
    assert label in (result / "report.md").read_text()
    pages = list((result / "items").glob("*.md"))
    assert len(pages) == 1 and TITLE in pages[0].read_text()
    cases = ElementTree.parse(result / "requirements.xml").findall(f".//testcase[@name='{TITLE}']")
    assert len(cases) == 1
    if junit_child:
        assert cases[0].find(junit_child) is not None
    else:
        assert cases[0].find("failure") is None and cases[0].find("skipped") is None
