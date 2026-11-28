"""OpenAPIの参照とパラメーターの優先順を検証する。"""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType


def test_operation_overrides_path_parameter_and_resolves_pointer(
    portal_module: Callable[[str], ModuleType],
) -> None:
    """JSON Pointerを解決し、同名のパス共通パラメーターを操作側で上書きする"""
    parameters = portal_module("content.openapi_fields").parameters
    spec = {"components": {"parameters": {"a/b": {"name": "q", "in": "query", "required": True}}}}
    path = {
        "parameters": [{"name": "q", "in": "query", "required": False}, {"name": "key", "in": "path"}]
    }
    op = {"parameters": [{"$ref": "#/components/parameters/a~1b"}]}
    assert parameters(spec, path, op) == [spec["components"]["parameters"]["a/b"], path["parameters"][1]]
