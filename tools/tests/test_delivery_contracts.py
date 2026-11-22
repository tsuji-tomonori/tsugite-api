import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from tools import mutation_test

ROOT = Path(__file__).resolve().parents[2]


def test_commit_message_hook(tmp_path: Path) -> None:
    """コミットフックが規約に沿った件名を許可し、規約外の件名を理由付きで拒否する。"""
    for folder in (".githooks", "tools/vendor/git-secrets"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    message = tmp_path / "COMMIT_EDITMSG"
    for subject, allowed in (("test(api): 申請を検証", True), ("変更しました", False)):
        message.write_text(subject + "\n", encoding="utf-8")
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=.githooks", "hook", "run", "commit-msg", "--", message.name],
            cwd=tmp_path,
            capture_output=True,
        )
        assert (result.returncode == 0) == allowed
        if not allowed:
            assert b"Conventional Commits" in result.stderr


def test_merge_deploy_workflow() -> None:
    """mainへのマージを検証した後だけOIDCで配備し、PRでは検証を実行する。"""
    import yaml

    def workflow(name: str) -> dict[str, Any]:
        source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.load(source, Loader=yaml.BaseLoader)
        return data

    verify = workflow("check.yml")
    cd = workflow("deploy.yml")
    assert verify["on"]["pull_request"]["branches"] == ["main"]
    assert cd["on"] == {"push": {"branches": ["main"]}}
    deploy = cd["jobs"]["deploy"]
    assert deploy["environment"] == "main" and deploy["permissions"]["id-token"] == "write"
    assert (
        deploy["needs"] == "verify-merge"
        and "needs.verify-merge.outputs.merged == 'true'" in deploy["if"]
    )
    steps = deploy["steps"]
    auth = next(
        i for i, step in enumerate(steps) if "configure-aws-credentials@" in step.get("uses", "")
    )
    assert steps[auth]["with"]["role-to-assume"] == "${{ vars.AWS_DEPLOY_ROLE_ARN }}"
    assert any("tools/manage.py deploy" in step.get("run", "") for step in steps[auth + 1 :])


def test_mutation_verdict() -> None:
    """変異後のアサーション失敗を検出に数え、収集エラーやスキップを検出件数から除く。"""

    def case(tag: str) -> ElementTree.Element:
        element = ElementTree.Element("testcase")
        ElementTree.SubElement(element, tag)
        return element

    assert mutation_test.detected(1, [case("failure")])
    assert not mutation_test.detected(0, [case("skipped")])
    assert not mutation_test.detected(1, [case("error"), case("failure")])
    assert not mutation_test.detected(2, [case("failure")])
