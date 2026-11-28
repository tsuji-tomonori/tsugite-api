"""ダミーのブラウザー境界を用意する。"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def portal_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], ModuleType]]:
    """PyScriptのブラウザー境界だけを代替し、画面モジュールを読み込む。"""
    source = Path(__file__).resolve().parents[1] / "src/web_app"
    previously_loaded = set(sys.modules)
    monkeypatch.syspath_prepend(str(source))
    monkeypatch.syspath_prepend(str(source.parents[2] / "backend/src/app/core"))
    js = ModuleType("js")
    js.__dict__.update(document=None, window=SimpleNamespace(sessionStorage={}))
    monkeypatch.setitem(sys.modules, "js", js)
    pyodide = ModuleType("pyodide")
    pyodide.__dict__["http"] = ModuleType("pyodide.http")
    pyodide.http.pyfetch = None
    monkeypatch.setitem(sys.modules, "pyodide", pyodide)
    monkeypatch.setitem(sys.modules, "pyodide.http", pyodide.http)
    yield import_module
    for name in set(sys.modules) - previously_loaded:
        file = getattr(sys.modules[name], "__file__", None)
        if name.startswith("pages.") or (file and Path(file).is_relative_to(source)):
            sys.modules.pop(name)
