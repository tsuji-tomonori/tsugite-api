import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def portal_module(monkeypatch):
    """PyScriptのブラウザー境界だけを代替し、画面モジュールを読み込む。"""
    module_names = {
        "api_docs",
        "chat_views",
        "client",
        "login_views",
        "portal_auth",
        "guide_content",
        "guide_search",
        "guide_views",
        "openapi_fields",
        "product_views",
    }
    previously_loaded = module_names & sys.modules.keys()
    source = Path(__file__).resolve().parents[1] / "src/web_app"
    monkeypatch.syspath_prepend(str(source))
    js = ModuleType("js")
    js.document = None
    js.window = SimpleNamespace(sessionStorage={})
    monkeypatch.setitem(sys.modules, "js", js)
    pyodide = ModuleType("pyodide")
    pyodide.http = ModuleType("pyodide.http")
    pyodide.http.pyfetch = None
    monkeypatch.setitem(sys.modules, "pyodide", pyodide)
    monkeypatch.setitem(sys.modules, "pyodide.http", pyodide.http)
    yield import_module
    for name in module_names - previously_loaded:
        sys.modules.pop(name, None)
