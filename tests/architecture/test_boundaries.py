from pathlib import Path

from pytestarch import Rule, get_evaluable_architecture


def test_persistence_has_no_http_dependencies():
    root = Path("backend/src").resolve()
    architecture = get_evaluable_architecture(root / "app", root / "app")
    Rule().modules_that().are_sub_modules_of(
        "app.db"
    ).should_not().import_modules_that().are_sub_modules_of("app.apis").assert_applies(architecture)


def test_published_operations_have_stable_ids():
    from app.main import create_app

    schema = create_app().openapi()
    expected = {"catalog", "me", "register", "detail", "publish", "apply", "requests", "decide", "audit"}
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert expected <= ids
    for operation in expected:
        assert Path("backend/src/app/apis/catalog", operation, "router.py").is_file()
