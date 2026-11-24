# DB層はHTTPのルーターに依存しない。
from ..core.project import ROOT


def test_persistence_has_no_http_dependencies():
    """DB層はHTTPのルーターに依存しない"""
    from pytestarch import get_evaluable_architecture

    root = ROOT / "packages/database/src/tsugite_db"
    architecture = get_evaluable_architecture(root, root, exclude_external_libraries=False)
    assert "tsugite_db.models" in architecture.modules
    assert not {m for m in architecture.modules if m == "app" or m.startswith("app.")}
