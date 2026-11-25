# 機能変更を要件の変更履歴と証跡に結びつける規約を検査する。
"""機能の変更と要件・証跡の保守がPRの必須検査として結び付いていることを確認する。"""

import subprocess
from pathlib import Path

import pytest
import yaml

from packages.tools.design.requirements import ITEMS, Requirement, check_maintenance

from .project import ROOT


@pytest.fixture
def change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "core.hooksPath=/dev/null", *args], text=True
        ).strip()

    def commit(subject):
        git("add", ".")
        git("commit", "-qm", subject)
        return git("rev-parse", "HEAD")

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    ITEMS.mkdir(parents=True)
    item = ITEMS / "既存要件.md"
    item.write_text("既存要件\n\n### 変更履歴\n\n- 2026-11-20 元の動作を定めた。\n")
    return commit("docs: 初期状態"), item, commit


def test_feature_signals_require_new_item(change):
    """ブランチ、PR件名・本文、コミットのいずれかで示された機能追加には新規要件を求める。"""
    base, _, commit = change
    Path("変更").write_text("機能")
    commit("fix: 通常の変更")
    for branch, title, body in (
        ("feature/catalog", "", ""),
        ("fix/catalog", "feat(api)!: 追加", ""),
        ("fix/catalog", "", "- feat: 商品追加"),
        ("fix/catalog", "", "要件への影響：機能追加"),
    ):
        with pytest.raises(ValueError, match="新規"):
            check_maintenance(branch, base, [], title, body)
    Path("変更").write_text("追加")
    commit("feat(api): 商品追加")
    with pytest.raises(ValueError, match="新規"):
        check_maintenance("fix/catalog", base, [], "", "要件への影響なし：内部変更")


def test_changed_item_requires_new_reason(change):
    """既存の履歴の使い回しを拒否し、同じPRで追記した日付と理由だけを受け付ける。"""
    base, path, commit = change
    original = path.read_text()
    path.write_text("変更後" + original)
    commit("docs: 動作を更新")

    def verify():
        check_maintenance(
            "docs/catalog", base, [Requirement(path, "利用者", set(), path.read_text())], "", ""
        )

    with pytest.raises(ValueError, match="変更理由"):
        verify()
    path.write_text(path.read_text() + "- 2026-11-25 申請画面を分離したため。\n")
    commit("docs: 理由を追記")
    verify()


def test_runtime_change_declares_impact(change):
    """実装だけの差分ではテンプレート内のコメントを除き、要件が変わらない理由を求める。"""
    base, _, commit = change
    code = Path("packages/backend/src/app.py")
    code.parent.mkdir(parents=True)
    code.write_text("value = 1")
    commit("refactor: 分割")
    with pytest.raises(ValueError, match="影響なし"):
        check_maintenance("refactor/demo", base, [], "", "<!--\n要件への影響なし：例\n-->")
    check_maintenance(
        "refactor/demo", base, [], "", "要件への影響なし：実装を同一パッケージ内で分割した。"
    )


def test_pull_request_checks_requirements_and_evidence():
    """PRの本文変更でも要件差分を検査し、同一コミットで受入テストの証跡を生成する。"""
    workflow = yaml.load((ROOT / ".github/workflows/check.yml").read_text(), Loader=yaml.BaseLoader)
    assert "edited" in workflow["on"]["pull_request"]["types"]
    steps = [step for job in workflow["jobs"].values() for step in job["steps"]]
    gate = next(
        step for step in steps if "packages/tools/design/requirements.py --branch" in step.get("run", "")
    )
    assert "if" not in gate
    assert gate["env"]["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    assert gate["env"]["PR_BODY"] == "${{ github.event.pull_request.body }}"
    assert gate["env"]["BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
    assert any("requirement_evidence --check" in step.get("run", "") for step in steps)
    assert any(
        step.get("env", {}).get("EVIDENCE_COMMIT") == "${{ github.event.pull_request.head.sha }}"
        for step in steps
    )
