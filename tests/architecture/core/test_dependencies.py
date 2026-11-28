# 全実装のインポートを調べ、配布単位を越える未許可の依存を検出する。
from .dependencies import ALLOWED, dependency_violations, layer, source_module
from .project import ROOT, project_files


def test_runtime_dependencies_respect_layer_boundaries():
    """全実装のインポートを調べ、配布単位を越える未許可の依存を検出する。"""
    covered, errors = set(), []
    for path in project_files(ROOT, ".py"):
        relative = path.relative_to(ROOT)
        if "tests" in relative.parts or path.name == "conftest.py":
            continue
        covered.add(layer(source_module(relative)))
        errors.extend(dependency_violations(relative, path.read_bytes()))
    assert covered == set(ALLOWED), f"検査できていない層: {set(ALLOWED) - covered}"
    assert not errors, "\n".join(errors)
