import json

import pytest

from .project import ROOT


def manifest_errors(manifest):
    errors = []
    for role, items in manifest.items():
        weights = [item for item in items if item["name"].endswith((".onnx", ".gguf"))]
        if not weights:
            errors.append(f"{role}: モデル重みがありません")
        for item in items:
            revision = item.get("revision", "")
            if not 7 <= len(revision) <= 40 or any(ch not in "0123456789abcdef" for ch in revision):
                errors.append(f"{role}/{item['name']}: 取得元をコミットで固定してください")
        for item in weights:
            digest = item.get("sha256", "")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                errors.append(f"{role}/{item['name']}: 重みのSHA-256が必要です")
    return errors


@pytest.mark.skipif(
    not ((ROOT / "agent").exists()),
    reason="エージェント未導入の構成",
)
def test_models_have_pinned_artifacts():
    """判定・検索語生成・回答生成の各モデルは取得元の版と重みのハッシュを固定する。"""
    manifest = json.loads((ROOT / "agent/models/manifest.json").read_text(encoding="utf-8"))
    assert {"decision", "tool", "generate"} <= manifest.keys()
    assert not (errors := manifest_errors(manifest)), errors
