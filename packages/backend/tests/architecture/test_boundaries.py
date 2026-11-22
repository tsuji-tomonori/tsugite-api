from pathlib import Path

from pytestarch import get_evaluable_architecture


def test_persistence_has_no_http_dependencies():
    root = Path("packages/database/src/tsugite_db").resolve()
    architecture = get_evaluable_architecture(root, root, exclude_external_libraries=False)
    assert "tsugite_db.models" in architecture.modules
    assert not {m for m in architecture.modules if m == "app" or m.startswith("app.")}


def test_published_operations_have_stable_ids():
    from app.main import create_app

    schema = create_app().openapi()
    expected = {"catalog", "me", "register", "detail", "publish", "apply", "requests", "decide", "audit"}
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert expected <= ids
    for operation in expected:
        assert Path("packages/backend/src/app/apis/catalog", operation, "router.py").is_file()
