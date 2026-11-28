# DB層はHTTPのルーターに依存しない。
from ..core.project import ROOT


def test_persistence_has_no_http_dependencies():
    """DB層はHTTPのルーターに依存しない"""
    from pytestarch import get_evaluable_architecture

    root = ROOT / "packages/database/src/tsugite_db"
    architecture = get_evaluable_architecture(root, root, exclude_external_libraries=False)
    assert "tsugite_db.models" in architecture.modules
    assert not {m for m in architecture.modules if m == "app" or m.startswith("app.")}


def test_model_files_match_registered_tables():
    """各テーブルと同名のファイルにモデルを1件置き、全モデルを共通のメタデータに登録する。"""
    from tsugite_db import models

    directory = ROOT / "packages/database/src/tsugite_db/models"
    modules = {path.stem for path in directory.glob("*.py")} - {"__init__", "base"}
    assert modules == set(models.Base.metadata.tables)
    for mapper in models.Base.registry.mappers:
        cls = mapper.class_
        assert cls.__module__ == f"tsugite_db.models.{mapper.local_table.name}"
        assert getattr(models, cls.__name__) is cls
