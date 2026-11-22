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
    monkeypatch.syspath_prepend(str(MODELS.parents[1] / "packages/backend/src/app/core"))
    for module, replacement in dependencies.items():
        if module == "runtime":
            replacement.logged_model.side_effect = lambda handler: handler
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


def test_generation_returns_grounded_result_from_warm_process(monkeypatch):
    """起動済みの生成モデルを再利用し、提示した資料の範囲と決定的な生成条件を渡す。"""
    import json

    worker = load_worker("completion", monkeypatch, runtime=Mock())
    monkeypatch.setenv("MODEL_ROLE", "generate")
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(worker, "process", process)
    request = Mock(side_effect=[{}, {"choices": [{"message": {"content": '{"source":0,"step":1}'}}]}])
    monkeypatch.setattr(worker, "request", request)
    event = {"question": "<検索>", "headings": ["手順"], "evidence": [["利用方法", ["開く", "選ぶ"]]]}
    assert worker.handler(event, None) == {"source": 0, "step": 1}
    assert request.call_args_list[0].args == ("/health",)
    path, payload = request.call_args.args
    assert path == "/v1/chat/completions"
    assert payload["temperature"] == 0 and payload["seed"] == 7
    assert json.loads(payload["messages"][1]["content"])["evidence"] == event["evidence"]
    schema = payload["response_format"]["schema"]
    assert schema["properties"]["source"]["enum"] == [0]
    assert schema["additionalProperties"] is False


def test_model_process_recovers_from_failed_health_check(monkeypatch):
    """応答しない生成プロセスを停止し、同じモデルをCPUで再起動して準備完了を待つ。"""
    worker = load_worker("completion", monkeypatch, runtime=Mock())
    old, new = Mock(), Mock()
    old.poll.return_value = new.poll.return_value = None
    worker.process = old
    start = Mock(return_value=new)
    request = Mock(side_effect=[OSError("unavailable"), {}])
    monkeypatch.setattr(worker.subprocess, "Popen", start)
    monkeypatch.setattr(worker, "model_file", Mock(return_value="/tmp/model.gguf"))
    monkeypatch.setattr(worker, "request", request)
    worker.ready("generate")
    old.kill.assert_called_once()
    old.wait.assert_called_once()
    arguments = start.call_args.args[0]
    assert arguments[arguments.index("--model") + 1] == "/tmp/model.gguf"
    assert arguments[arguments.index("--n-gpu-layers") + 1] == "0"
    assert worker.process is new and request.call_count == 2


def test_embedding_load_reuses_cpu_model_and_tokenizer(monkeypatch):
    """埋め込みモデルと長さ制限付きトークナイザーを初回だけ読み込む。"""
    ort, tokenizers, runtime = Mock(), Mock(), Mock()
    runtime.model_file.side_effect = lambda role, name: f"/tmp/{role}/{name}"
    worker = load_worker(
        "decision", monkeypatch, numpy=Mock(), onnxruntime=ort, tokenizers=tokenizers, runtime=runtime
    )
    session, tokenizer = worker.load()
    assert worker.load() == (session, tokenizer)
    options = ort.SessionOptions.return_value
    assert (options.inter_op_num_threads, options.intra_op_num_threads) == (1, 2)
    ort.InferenceSession.assert_called_once_with(
        "/tmp/decision/model.onnx", sess_options=options, providers=["CPUExecutionProvider"]
    )
    tokenizers.Tokenizer.from_file.assert_called_once_with("/tmp/decision/tokenizer.json")
    tokenizer.enable_truncation.assert_called_once_with(max_length=192)
    tokenizer.enable_padding.assert_called_once_with(pad_id=3, pad_token="[PAD]")
