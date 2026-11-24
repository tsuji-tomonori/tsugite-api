# 配備用コードとLayerだけでモデルを読み込み、外部パッケージの読み込み元を確認する。
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

BUILD = Path(__file__).resolve().parents[3] / "build"


@pytest.mark.parametrize(
    "code,layer,handler",
    [
        pytest.param(
            "chat-decision",
            "decision-model",
            "decision",
            marks=pytest.mark.case_detail("判定用の依存からネイティブ推論ライブラリを読み込む"),
        ),
        pytest.param(
            "chat-llm",
            "model-sdk",
            "completion",
            marks=pytest.mark.case_detail("生成用の依存からモデル取得用SDKを読み込む"),
        ),
    ],
)
def test_model_imports_from_deployment_packages(tmp_path, code, layer, handler):
    """配備用コードとLayerだけでモデルを読み込み、外部パッケージの読み込み元を確認する。"""
    code_dir = BUILD / code
    layer_dir = tmp_path / "opt"
    with ZipFile(BUILD / f"{layer}-layer.zip") as archive:
        archive.extractall(layer_dir)
    script = """
import importlib
import importlib.util
import sys
from pathlib import Path
code, dependencies, handler = sys.argv[1:]
sys.path[:0] = [code, dependencies]
module = importlib.import_module(handler)
assert Path(module.__file__).parent == Path(code)
names = ["boto3"]
if handler == "decision":
    names.extend(["numpy", "onnxruntime", "tokenizers"])
    assert "CPUExecutionProvider" in importlib.import_module("onnxruntime").get_available_providers()
else:
    assert not any(importlib.util.find_spec(name) for name in ("onnxruntime", "numpy", "tokenizers"))
for name in names:
    assert Path(importlib.import_module(name).__file__).is_relative_to(dependencies), name
"""
    subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(code_dir), str(layer_dir / "python"), handler],
        cwd=tmp_path,
        check=True,
    )


def test_agent_imports_from_worker_deployment_package(tmp_path):
    """配備用コードとLayerだけでワーカーを読み込み、同梱ガイドを使って回答を生成できる。"""
    code = BUILD / "lambda"
    with ZipFile(BUILD / "runtime-layer.zip") as archive:
        archive.extractall(tmp_path)
    script = """
import sys
from pathlib import Path
code, dependencies = sys.argv[1:]
sys.path[:0] = [code, dependencies]
from agent import jobs
from app.core.auth import Actor
assert Path(jobs.__file__).resolve().is_relative_to(code)
assert callable(jobs.handler)
assert not Path(code, "agent/models").exists()
viewer = Actor("consumer", frozenset(), frozenset(), False, False)
result = jobs.ask("APIキーを発行する手順を教えて", lambda: [], viewer, lambda *_: {})
assert result["kind"] == "manual" and result["keys"]
"""
    subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--python",
            "3.15",
            "python",
            "-I",
            "-S",
            "-c",
            script,
            str(code),
            str(tmp_path / "python"),
        ],
        cwd=tmp_path,
        check=True,
        timeout=120,
    )
