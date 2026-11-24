# エージェントが利用する推論モデルの配布条件を検証する。
from ..core.project import ROOT
from .model_artifacts import check_model_artifacts


def test_agent_distributes_pinned_models():
    """エージェントが使う推論モデルの役割、取得元、ハッシュを検査する。"""
    check_model_artifacts(ROOT / "packages/agent/src/agent/models")
