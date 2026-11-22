from .project import ROOT


def test_persistence_has_no_http_dependencies():
    """DB層はHTTPのルーターに依存しない"""
    from pytestarch import get_evaluable_architecture

    root = ROOT / "packages/database/src/tsugite_db"
    architecture = get_evaluable_architecture(root, root, exclude_external_libraries=False)
    assert "tsugite_db.models" in architecture.modules
    assert not {m for m in architecture.modules if m == "app" or m.startswith("app.")}


def test_published_operations_have_stable_ids():
    """公開操作のOpenAPI IDと実装が対応する"""
    from app.main import create_app

    schema = create_app().openapi()
    expected = {"catalog", "me", "register", "detail", "publish", "apply", "requests", "decide", "audit"}
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert expected <= ids
    for operation in expected:
        assert (ROOT / "packages/backend/src/app/apis/catalog" / operation / "router.py").is_file()
