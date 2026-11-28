"""エージェントのジョブと検索が専用のパッケージから配布されることを検証する。"""

import tomllib

from ..core.project import ROOT


def test_agent_publishes_flat_worker_modules():
    """ワーカーと検索をsrc直下から配布し、推論ワーカーを同梱しない。"""
    package = ROOT / "packages/agent"
    config = tomllib.loads((package / "pyproject.toml").read_text())
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["sources"] == ["src"]
    modules = {p.stem for p in (package / "src").rglob("*.py")}
    assert {"chat_jobs", "chat_retrieval"} <= modules
    assert not modules.intersection({"completion", "decision", "model_runtime"})
