"""モデル配布物の役割とハッシュを検証する。"""

import json


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


def check_model_artifacts(directory):
    """モデルを含む配布物には三つの役割と版・ハッシュが必要。"""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    missing = {"decision", "tool", "generate"} - manifest.keys()
    assert not missing, f"不足しているモデルの役割: {sorted(missing)}"
    assert not (errors := manifest_errors(manifest)), errors
