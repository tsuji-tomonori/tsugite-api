"""推論サービスとの境界だけを置き換えて、Lambdaの入力処理とモデル取得を検証する。"""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MODELS = Path(__file__).resolve().parents[3] / "agent/models"


def load_worker(name, monkeypatch, **dependencies):
    for module, replacement in dependencies.items():
        monkeypatch.setitem(sys.modules, module, replacement)
    spec = importlib.util.spec_from_file_location(name, MODELS / f"{name}.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


def test_embedding_reuses_vectors_and_validates_batch(monkeypatch):
    """重複する入力の埋め込みを再利用し、空のバッチは推論前に拒否する。"""
    worker = load_worker(
        "decision",
        monkeypatch,
        numpy=Mock(),
        onnxruntime=Mock(),
        tokenizers=Mock(),
        runtime=Mock(),
    )
    encode = Mock(return_value=SimpleNamespace(tolist=lambda: [[1.0], [2.0]]))
    monkeypatch.setattr(worker, "encode", encode)
    assert worker.handler({"texts": ["商品", "手順", "商品"]}, None) == {
        "vectors": [[1.0], [2.0], [1.0]]
    }
    assert worker.handler({"texts": ["手順"]}, None) == {"vectors": [[2.0]]}
    with pytest.raises(ValueError, match="Invalid embedding batch"):
        worker.handler({"texts": []}, None)
    encode.assert_called_once_with(["商品", "手順"])


def test_completion_limits_tool_choices(monkeypatch):
    """検索モデルへの選択肢を許可された操作に限定し、候補が空ならモデルを呼び出さない。"""
    worker = load_worker("completion", monkeypatch, runtime=Mock())
    monkeypatch.setenv("MODEL_ROLE", "tool")
    complete = Mock(return_value={"action": "catalog", "query": "在庫"})
    monkeypatch.setattr(worker, "complete", complete)
    assert worker.handler({"allowed": ["delete"]}, None) == {}
    result = worker.handler({"allowed": ["catalog", "delete"], "question": "在庫"}, None)
    assert result == {"action": "catalog", "query": "在庫"}
    complete.assert_called_once()
    assert complete.call_args.args[3]["properties"]["action"] == {"enum": ["catalog"]}


def test_model_download_verifies_digest_before_reuse(monkeypatch, tmp_path):
    """モデルのハッシュが異なる場合は一時ファイルを破棄し、正しいモデルを取得した後は再利用する。"""
    s3 = Mock()
    worker = load_worker("runtime", monkeypatch, boto3=SimpleNamespace(client=lambda _: s3))
    monkeypatch.setenv("MODEL_BUCKET", "models")
    monkeypatch.setattr(worker, "Path", lambda _: tmp_path)
    item = {"name": "model.bin", "revision": "v1", "sha256": hashlib.sha256(b"valid").hexdigest()}
    monkeypatch.setattr(worker, "manifest", lambda: {"decision": [item]})
    content = iter([b"bad", b"valid"])
    s3.download_file.side_effect = lambda bucket, key, dest: Path(dest).write_bytes(next(content))
    with pytest.raises(ValueError, match="checksum"):
        worker.model_file("decision", "model.bin")
    assert not list(tmp_path.iterdir())
    model = worker.model_file("decision", "model.bin")
    assert Path(model).read_bytes() == b"valid"
    assert worker.model_file("decision", "model.bin") == model
    assert s3.download_file.call_count == 2
