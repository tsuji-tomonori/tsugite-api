"""推論ワーカーを単独で配備できることを、配布されたモジュールの読み込みで確認する。"""

import subprocess
import sys
import textwrap

import pytest

from packages.tools.packaging import build_chat


@pytest.mark.parametrize(
    ("package", "worker"),
    [
        pytest.param(
            "chat-decision",
            "decision",
            marks=pytest.mark.case_detail("判定関数は業務パッケージなしで読み込める"),
        ),
        pytest.param(
            "chat-llm",
            "completion",
            marks=pytest.mark.case_detail("生成関数は業務パッケージと判定用依存なしで読み込める"),
        ),
    ],
)
def test_packaged_worker_imports_independently(tmp_path, monkeypatch, package, worker):
    """推論関数の配布物から業務パッケージを読み込まずにハンドラーを起動準備できる。"""
    monkeypatch.setattr(build_chat, "BUILD", tmp_path)
    build_chat.stage()
    program = textwrap.dedent("""
        import importlib
        import sys
        from pathlib import Path
        from types import ModuleType

        source, entry = sys.argv[1:]
        forbidden = {"app", "agent", "tsugite_db", "sample_api", "infra_app", "packages", "web_app"}
        native_dependencies = {"numpy", "onnxruntime", "tokenizers"}
        if entry == "completion":
            forbidden.update(native_dependencies)
        else:
            for name in native_dependencies:
                module = ModuleType(name)
                if name == "tokenizers":
                    module.Tokenizer = object
                sys.modules[name] = module

        class DeploymentBoundary:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in forbidden:
                    raise AssertionError(f"配布対象外への依存 {fullname}")

        sys.meta_path.insert(0, DeploymentBoundary())
        sys.path.insert(0, source)
        worker = importlib.import_module(entry)
        assert Path(worker.__file__).resolve().parent == Path(source).resolve()
        assert callable(worker.handler)
    """)
    subprocess.run([sys.executable, "-I", "-c", program, str(tmp_path / package), worker], check=True)
