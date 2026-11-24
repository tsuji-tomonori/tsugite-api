from pathlib import Path

import pytest

from tools.design import completion


def test_workflow_comments_follow_steps():
    """検査の直前の説明と実行条件を対応付け、シェル文字列内の偽コメントを無視する。"""
    workflow = """jobs:
  test:
    steps:
      # 実行準備
      - run: |
          #: シェル内のコメント
          echo OK
      #: 型の不一致を検出する。
      - name: 型検査
        if: steps.scope.outputs.types == 'true'
        run: task types
"""
    rows = list(completion.workflow_checks(workflow, lambda title, path, line: (title, line)))
    assert rows == [(("型検査", 9), "型の不一致を検出する。", "`steps.scope.outputs.types == 'true'`")]
    with pytest.raises(ValueError, match="検査の説明"):
        list(completion.workflow_checks(workflow.replace("#: 型", "# 型"), lambda *args: ""))


def test_rule_changes_and_test_edits_reach_document(tmp_path, monkeypatch):
    """ブランチの下限・低下幅を合成し、非同期テストとクラスの説明を定義行から取得する。"""
    rules = [
        {"type": "code_coverage", "parameters": {"minimum_coverage": 71, "max_coverage_drop": 2}},
        {"type": "code_coverage", "parameters": {"minimum_coverage": 89, "max_coverage_drop": 0.5}},
    ]
    result = completion.render(rules, "sample", "../../")
    assert "89%以上" in result and "0.5ポイント以内" in result
    assert "全体の最低行カバレッジ | 下限指定なし" in completion.render([], "sample", "../../")
    assert "フロントエンド" in result and "アーキテクチャ" in result
    for suite, label in completion.ci_scope.parallel_packages().items():
        section = result.split(f"### {label}（", 1)[1].split("\n### ", 1)[0]
        assert f"({suite}/" in section.replace("(../../", "(")
    suite = tmp_path / "cases"
    suite.mkdir()
    path = suite / "test_feature.py"
    path.write_text(
        'class TestFeature:\n    @pytest.mark.case_detail("画面を初めて開く場合")\n    async def test_start(self):\n        """起動すると状態を表示する。"""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(completion, "ROOT", tmp_path)
    assert list(completion.test_rows(suite, lambda owner, file, line: (owner, file, line))) == [
        (
            "起動すると状態を表示する。",
            "画面を初めて開く場合",
            ("TestFeature.test_start", Path("cases/test_feature.py"), 3),
        )
    ]
