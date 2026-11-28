"""CDKが指定した認証ハンドラーを専用パッケージから配布できることを確認する。"""

import ast
import tomllib

from tests.architecture.core.project import ROOT


def test_authorizer_handler_belongs_to_api_auth():
    """CDKのAccess関数に指定したモジュールと関数が認証パッケージの配布対象にある。"""
    runtime = ROOT / "packages/infra/src/components/runtime.py"
    calls = [
        node
        for node in ast.walk(ast.parse(runtime.read_bytes()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "catalog_function"
        and ast.literal_eval(node.args[1]) == "Access"
    ]
    (call,) = calls
    module, function = ast.literal_eval(call.args[2]).rsplit(".", 1)
    package = ROOT / "packages/api-auth"
    wheel = tomllib.loads((package / "pyproject.toml").read_text())["tool"]["hatch"]["build"]["targets"][
        "wheel"
    ]
    source = package / "src" / (module.replace(".", "/") + ".py")
    assert any(source.is_relative_to(package / folder) for folder in wheel["packages"])
    assert function in {
        node.name for node in ast.parse(source.read_bytes()).body if isinstance(node, ast.FunctionDef)
    }
