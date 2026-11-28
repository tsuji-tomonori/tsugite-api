"""チャットの判断処理が独立したパッケージから配布されることを検証する。"""

import tomllib

from ..core.project import ROOT


def test_agent_publishes_flat_worker_modules():
    """検索の判断処理を単独で配布し、ジョブの永続化をバックエンドに限定する。"""
    package = ROOT / "packages/agent"
    config = tomllib.loads((package / "pyproject.toml").read_text())
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["sources"] == ["src"]
    modules = {p.stem for p in (package / "src").rglob("*.py")}
    assert "chat_retrieval" in modules
    assert config["project"]["dependencies"] == []
    assert not modules.intersection({"completion", "decision", "model_runtime", "chat_jobs"})
