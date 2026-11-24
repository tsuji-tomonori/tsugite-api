# 行カバレッジのブランチルールと比較元を独立した小さな計測値で検証する。
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest

from packages.tools.ci import check_coverage


def code_rule(floor, drop):
    return {
        "type": "code_coverage",
        "parameters": {"minimum_coverage": floor, "max_coverage_drop": drop},
    }


def measured(folder, covered, total=100):
    report = folder / "coverage.xml"
    report.write_text(
        f'<coverage lines-covered="{covered}" lines-valid="{total}" line-rate="{covered / total}"/>'
    )
    return report


@pytest.mark.parametrize(
    ("current", "floor", "allowance", "base", "pass_gate"),
    [
        pytest.param(
            84,
            84,
            1,
            85,
            True,
            id="at-both-limits",
            marks=pytest.mark.case_detail("下限と低下幅がともに境界なら合格する"),
        ),
        pytest.param(
            83,
            84,
            1,
            83,
            False,
            id="under-floor",
            marks=pytest.mark.case_detail("低下がなくても最低行カバレッジ未満なら失敗する"),
        ),
        pytest.param(
            88,
            84,
            1,
            90,
            False,
            id="large-drop",
            marks=pytest.mark.case_detail("下限を満たしていても低下幅を超えたら失敗する"),
        ),
        pytest.param(
            88,
            84,
            0,
            99,
            True,
            id="disabled-drop",
            marks=pytest.mark.case_detail("低下幅の判定を無効にしたルールでは下限だけを使う"),
        ),
        pytest.param(
            100,
            90,
            1,
            95,
            True,
            id="improved",
            marks=pytest.mark.case_detail("改善した計測は低下幅の判定に合格する"),
        ),
    ],
)
def test_branch_gate(tmp_path, monkeypatch, current, floor, allowance, base, pass_gate):
    """PRの行カバレッジを対象ブランチの最低値と許容低下幅の両方で判定する。"""
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/project")
    monkeypatch.setenv("BASE_BRANCH", "release/test")
    monkeypatch.setenv("BASE_SHA", "base-sha")
    rules_api = Mock(return_value=[code_rule(floor, allowance)])
    monkeypatch.setattr(check_coverage, "github_json", rules_api)
    monkeypatch.setattr(check_coverage, "baseline_coverage", lambda *args: base)
    path = measured(tmp_path, current)
    if pass_gate:
        check_coverage.main(path)
    else:
        with pytest.raises(ValueError, match="coverage"):
            check_coverage.main(path)
    assert "release%2Ftest" in rules_api.call_args.args[0]


def test_combined_branch_rules_and_exact_measurement(tmp_path):
    """複数のルールから厳しい下限と有効な低下幅を選び、行数から正確な割合を得る。"""
    rules = [code_rule(83, 0), {"type": "required_status_checks"}, code_rule(84, 5), code_rule(79, 1)]
    assert check_coverage.coverage_limits(rules) == (84, 1)
    assert check_coverage.coverage_limits([]) == (0, 0)
    assert check_coverage.line_coverage(measured(tmp_path, 169, 200)) == Decimal("84.5")


def test_baseline_prefers_saved_aggregate_and_measures_missing(monkeypatch, tmp_path):
    """保存済みの合算結果を再利用し、取得できない場合だけ比較元コミットを計測する。"""
    cached = Mock(return_value=Decimal(87))
    measured_base = Mock(return_value=Decimal(91))
    monkeypatch.setattr(check_coverage, "merged_pr_coverage", cached)
    monkeypatch.setattr(check_coverage, "measure_base_coverage", measured_base)
    monkeypatch.chdir(tmp_path)
    assert check_coverage.baseline_coverage("org/project", "main", "base") == 87
    measured_base.assert_not_called()
    cached.return_value = None
    assert check_coverage.baseline_coverage("org/project", "main", "base") == 91
    measured_base.assert_called_once_with("base")


def test_github_rules_are_requested_as_json(monkeypatch):
    """GitHubのブランチルールをJSONで読み、取得したルールから下限を取り出す。"""
    response = [code_rule(92, 2)]
    cli = Mock(return_value=json.dumps(response).encode())
    monkeypatch.setattr("subprocess.check_output", cli)
    rules = check_coverage.branch_rules("org/project", "main")
    assert check_coverage.coverage_limits(rules) == (92, 2)
    assert "repos/org/project/rules/branches/main" in cli.call_args.args[0]


@pytest.mark.parametrize(
    ("same_tree", "expired", "available"),
    [
        pytest.param(
            True,
            False,
            True,
            id="verified",
            marks=pytest.mark.case_detail("同一ツリーの検証済みPRの計測を取得する"),
        ),
        pytest.param(
            False,
            False,
            False,
            id="changed-tree",
            marks=pytest.mark.case_detail("マージ時に内容が変わったPRの計測を再利用しない"),
        ),
        pytest.param(
            True,
            True,
            False,
            id="expired",
            marks=pytest.mark.case_detail("有効期限切れの計測を再利用しない"),
        ),
    ],
)
def test_baseline_download_verifies_source_and_artifact(
    tmp_path, monkeypatch, same_tree, expired, available
):
    """マージ済みPRの計測はツリーの一致と有効な成果物を確認できた場合だけ使用する。"""
    repository = "example/project"
    merge, head = "merged-commit", "tested-commit"
    pr = {
        "number": 17,
        "merged_at": "2026-01-01",
        "merge_commit_sha": merge,
        "head": {"sha": head, "repo": {"full_name": repository}},
        "base": {"ref": "main", "repo": {"full_name": repository}},
    }
    responses = {
        f"commits/{merge}/pulls": [pr],
        f"git/commits/{merge}": {
            "tree": {"sha": "merged-tree"},
            "parents": [{"sha": "old"}, {"sha": head}],
        },
        f"git/commits/{head}": {"tree": {"sha": "merged-tree" if same_tree else "different-tree"}},
        "actions/workflows/check.yml/runs": {
            "workflow_runs": [
                {"id": 123, "head_sha": head, "conclusion": "success", "event": "pull_request"}
            ]
        },
        "actions/runs/123/artifacts": {
            "artifacts": [{"name": "line-coverage", "expired": expired, "id": 70}]
        },
    }
    monkeypatch.setattr(
        check_coverage,
        "github_json",
        lambda endpoint, *args: responses[endpoint.removeprefix(f"repos/{repository}/")],
    )
    command = Mock()
    monkeypatch.setattr("subprocess.run", command)
    assert check_coverage.download_merged_coverage(repository, "main", merge, tmp_path) == available
    if available:
        args = command.call_args.args[0]
        assert "123" in args and "line-coverage" in args and str(tmp_path) in args
    else:
        command.assert_not_called()
