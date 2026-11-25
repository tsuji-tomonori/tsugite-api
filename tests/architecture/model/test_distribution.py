# 推論モデルの配布条件を検証する。
from ..core.project import ROOT
from .model_artifacts import check_model_artifacts


def test_model_distributes_pinned_weights():
    """エージェントが使う推論モデルの役割、取得元、ハッシュを検査する。"""
    check_model_artifacts(ROOT / "packages/model/src")
