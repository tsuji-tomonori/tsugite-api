from packages.frontend.src.web_app.openapi_fields import parameters


def test_operation_overrides_path_parameter_and_resolves_pointer():
    """JSON Pointerを解決し、同名のパス共通パラメーターを操作側で上書きする"""
    spec = {"components": {"parameters": {"a/b": {"name": "q", "in": "query", "required": True}}}}
    path = {
        "parameters": [{"name": "q", "in": "query", "required": False}, {"name": "key", "in": "path"}]
    }
    op = {"parameters": [{"$ref": "#/components/parameters/a~1b"}]}
    assert parameters(spec, path, op) == [spec["components"]["parameters"]["a/b"], path["parameters"][1]]
