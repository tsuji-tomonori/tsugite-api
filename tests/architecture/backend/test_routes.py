"""公開操作のOpenAPI IDと実装が対応する。"""

from ..core.project import ROOT


def test_published_operations_have_stable_ids():
    """公開操作のOpenAPI IDと実装が対応する"""
    from app.main import create_app

    schema = create_app().openapi()
    expected = {"catalog", "me", "register", "detail", "publish", "apply", "requests", "decide", "audit"}
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert expected <= ids
    for operation in expected:
        assert (ROOT / "packages/backend/src/app/apis/catalog" / f"{operation}.py").is_file()


def test_route_handlers_belong_to_api_layer():
    """FastAPIに登録した業務ルートはapis配下で定義し、下位層からルーターを参照しない。"""
    import ast

    from app.main import create_app
    from fastapi.routing import APIRoute, iter_route_contexts

    from ..core.dependencies import dependencies, source_module

    routes = list(iter_route_contexts(create_app().routes))
    modules = {
        route.original_route.endpoint.__module__
        for route in routes
        if isinstance(route.original_route, APIRoute)
    }
    assert modules
    assert all(module.startswith("app.apis.") or module == "app.main" for module in modules), modules
    for layer in ("core", "integrations"):
        for path in (ROOT / "packages/backend/src/app" / layer).rglob("*.py"):
            module = source_module(path.relative_to(ROOT))
            for line, imported in dependencies(ast.parse(path.read_bytes()), module.rpartition(".")[0]):
                assert not imported.startswith("app.apis."), f"{path}:{line}: {imported}"
