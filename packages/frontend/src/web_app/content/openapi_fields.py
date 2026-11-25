# OpenAPIの参照とパラメーターを解決する。
from __future__ import annotations

from typing import Any
from urllib.parse import unquote


def resolve(spec: dict[str, Any], node: Any) -> Any:
    """ローカル参照を循環せずに解決する。"""
    seen = set()
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in seen:
            break
        seen.add(ref)
        target = spec
        for part in unquote(ref[2:]).split("/"):
            name = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or name not in target:
                return node
            target = target[name]
        node = target
    return node


def parameters(
    spec: dict[str, Any], item: dict[str, Any], operation: dict[str, Any]
) -> list[dict[str, Any]]:
    """パスと操作のパラメーターを統合する。"""
    merged = {}
    for source in (item, operation):
        for raw in source.get("parameters", []):
            param = resolve(spec, raw)
            if isinstance(param, dict) and "name" in param and "in" in param:
                merged[(param["in"], param["name"])] = param
    return list(merged.values())
