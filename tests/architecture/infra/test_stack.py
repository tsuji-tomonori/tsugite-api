# CDKコンポーネントからスタック組み立て処理への逆向き依存を検出する。
import ast

from ..core.dependencies import dependencies, source_module
from ..core.project import ROOT


def test_components_do_not_import_the_stack():
    """CDKスタックが各コンポーネントを組み立て、コンポーネントからスタックを参照しない。"""
    package = ROOT / "packages/infra/src/infra_app"
    assert (package / "stack.py").is_file()
    errors = []
    for path in package.rglob("*.py"):
        if path == package / "stack.py":
            continue
        module = source_module(path.relative_to(ROOT))
        for line, imported in dependencies(ast.parse(path.read_bytes()), module.rpartition(".")[0]):
            if imported.split(".")[:2] == ["infra_app", "stack"]:
                errors.append(f"{path.relative_to(ROOT)}:{line}: {imported}")
    assert not errors, errors
