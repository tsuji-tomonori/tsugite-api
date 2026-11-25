# 推論Lambdaの応答・ウォーム再利用・外部推論の失敗を小さな入力で確認する。
import json
import sys
from collections import OrderedDict
from importlib import import_module, util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def workers(monkeypatch):
    packages = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(packages / "backend/src/app/core"))
    monkeypatch.syspath_prepend(str(packages / "model/src"))
    return import_module


@pytest.fixture
def decision_worker(workers, monkeypatch):
    for name in ("numpy", "onnxruntime", "tokenizers"):
        module = ModuleType(name)
        if name == "tokenizers":
            monkeypatch.setattr(module, "Tokenizer", Mock(), raising=False)
        monkeypatch.setitem(sys.modules, name, module)
    # テスト用の推論依存が他の呼び出しに残らないよう専用の名前でワーカーを読み込む。
    path = Path(__file__).resolve().parents[1] / "src/decision.py"
    spec = util.spec_from_file_location("required_embedding_worker", path)
    assert spec is not None and spec.loader is not None
    worker = util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


class VectorBatch(list):
    def tolist(self):
        return list(self)


def test_embedding_worker_reuses_each_text_and_preserves_batch_order(decision_worker, monkeypatch):
    """重複する文章は一度だけ推論し、ウォーム実行でも入力順に対応する埋め込みを返す。"""
    worker = decision_worker

    reference = {"在庫": [1, 0], "納期": [0, 1], "請求": [1, 1]}

    def encode(texts):
        return VectorBatch(reference[text] for text in texts)

    infer = Mock(side_effect=encode)
    monkeypatch.setattr(worker, "encode", infer)
    monkeypatch.setattr(worker, "vectors", OrderedDict())
    assert worker.handler({"texts": ["納期", "在庫", "納期"]}, None) == {
        "vectors": [[0, 1], [1, 0], [0, 1]]
    }
    assert worker.handler({"texts": ["在庫", "請求"]}, None) == {"vectors": [[1, 0], [1, 1]]}
    assert [list(call.args[0]) for call in infer.call_args_list] == [["納期", "在庫"], ["請求"]]
    with pytest.raises(ValueError, match="(?i)batch"):
        worker.handler({"texts": []}, None)
    assert infer.call_count == 2


@pytest.mark.parametrize(
    ("role", "payload", "chosen"),
    [
        pytest.param(
            "tool",
            {"allowed": ["catalog", "manual", "assign-role"]},
            {"action": "manual", "query": "在庫照会"},
            marks=pytest.mark.case_detail("検索語モデルの選択肢をカタログと手順の検索に限定する"),
        ),
        pytest.param(
            "generate",
            {
                "headings": ["操作手順", "参考資料"],
                "evidence": [["在庫ガイド", ["在庫を開く"]], ["商品一覧", ["商品を選ぶ"]]],
            },
            {"heading": "操作手順", "source": 1, "step": 0},
            marks=pytest.mark.case_detail("回答モデルの見出しと出典番号を渡された候補だけに限定する"),
        ),
    ],
)
def test_generation_workers_request_reproducible_schema_constrained_output(
    workers, monkeypatch, role, payload, chosen
):
    """各モデルは質問をデータとして送り、温度・シードと出力形式を固定して同じ構造の応答を返す。"""
    model = workers("completion")
    monkeypatch.setenv("MODEL_ROLE", role)
    monkeypatch.setattr(model, "ready", lambda role: None)
    transport = Mock(
        return_value={"choices": [{"message": {"content": json.dumps(chosen, ensure_ascii=False)}}]}
    )
    monkeypatch.setattr(model, "request", transport)
    event = {"question": "在庫はどこで照会できますか", **payload}
    for _ in range(2):
        assert model.handler(event, None) == chosen
    requests = [call.args[1] for call in transport.call_args_list]
    assert requests[0] == requests[1]
    prompt = requests[0]
    assert prompt["temperature"] == 0 and isinstance(prompt["seed"], int)
    assert json.loads(prompt["messages"][-1]["content"])["question"] == event["question"]
    assert prompt["messages"][-1]["role"] == "user"
    assert prompt["response_format"]["type"] == "json_schema"
    schema = prompt["response_format"]["schema"]
    assert set(schema["required"]) == set(chosen)
    assert schema["additionalProperties"] is False
    if role == "tool":
        assert set(schema["properties"]["action"]["enum"]) == {"manual", "catalog"}
    else:
        assert schema["properties"]["heading"]["enum"] == payload["headings"]
        assert schema["properties"]["source"]["enum"] == [0, 1]


def test_no_permitted_search_target_skips_inference(workers, monkeypatch):
    """業務更新だけが指定されて検索先が残らなければ、モデルを起動せず空の選択を返す。"""
    model = workers("completion")
    ready = Mock()
    monkeypatch.setattr(model, "ready", ready)
    monkeypatch.setenv("MODEL_ROLE", "tool")
    assert model.handler({"question": "問い合わせを送りたい", "allowed": ["submit-inquiry"]}, None) == {}
    ready.assert_not_called()


def test_broken_json_does_not_return_invented_search_action(workers, monkeypatch):
    """推論サービスの出力が壊れたJSONなら検索先や検索語を作らず、選択なしとして返す。"""
    model = workers("completion")
    monkeypatch.setenv("MODEL_ROLE", "tool")
    monkeypatch.setattr(model, "ready", lambda role: None)
    monkeypatch.setattr(
        model, "request", Mock(return_value={"choices": [{"message": {"content": "broken"}}]})
    )
    assert model.handler({"question": "在庫照会", "allowed": ["catalog"]}, None) == {}


def test_unavailable_inference_server_reports_failure_without_disclosing_question(
    workers, monkeypatch, capsys
):
    """生成サーバーに接続できなければ呼び出し失敗を通知し、エラーログに質問本文を含めない。"""
    model = workers("completion")
    monkeypatch.setenv("MODEL_ROLE", "generate")
    monkeypatch.setattr(model, "ready", lambda role: None)
    monkeypatch.setattr(model, "request", Mock(side_effect=ConnectionError("server unavailable")))
    message = "未公開の契約番号に関する質問"
    with pytest.raises(ConnectionError, match="server unavailable"):
        model.handler({"question": message, "evidence": [], "headings": ["操作手順"]}, None)
    output = capsys.readouterr()
    log = output.out + output.err
    assert "model.failure" in log
    assert message not in log


def test_warm_embedding_cache_keeps_recent_queries_and_recomputes_old_texts(
    decision_worker, monkeypatch
):
    """多数の異なる質問が続いた後でも直近の埋め込みを再利用し、古い質問は正しく再計算する。"""

    def encode(texts):
        return VectorBatch([[int(text)] for text in texts])

    infer = Mock(side_effect=encode)
    monkeypatch.setattr(decision_worker, "encode", infer)
    for first in range(0, 1024, 8):
        inputs = [str(value) for value in range(first, first + 8)]
        decision_worker.handler({"texts": inputs}, None)
    infer.reset_mock()
    assert decision_worker.handler({"texts": ["1023", "0"]}, None) == {"vectors": [[1023], [0]]}
    infer.assert_called_once_with(["0"])


def test_non_dense_onnx_output_fails_the_embedding_request(decision_worker, monkeypatch):
    """ONNXが埋め込みの代わりに異なる型を返した場合は、検索に使えるベクトルとして返さない。"""
    tokenizer = Mock()
    tokenizer.encode_batch.return_value = [SimpleNamespace(ids=[2, 3], attention_mask=[1, 1])]
    session = Mock()
    session.get_inputs.return_value = [
        SimpleNamespace(name="input_ids"),
        SimpleNamespace(name="attention_mask"),
    ]
    session.run.return_value = [{"diagnostic": "no model output"}]
    array_api = SimpleNamespace(
        array=lambda values, *, dtype: list(values),
        int64=int,
        ndarray=tuple,
        zeros_like=lambda matrix: [[0 for value in row] for row in matrix],
    )
    monkeypatch.setattr(decision_worker, "np", array_api)
    monkeypatch.setattr(decision_worker, "load", lambda: (session, tokenizer))
    with pytest.raises(ValueError, match="(?i)embedding"):
        decision_worker.handler({"texts": ["在庫を確認"]}, None)
    tokenizer.encode_batch.assert_called_once_with(["在庫を確認"])
    session.run.assert_called_once_with(None, {"input_ids": [[2, 3]], "attention_mask": [[1, 1]]})


def test_decision_worker_loads_weights_and_tokenizer_from_layer(decision_worker, monkeypatch):
    """判定は専用レイヤーの重みとトークナイザーを使い、二度目には同じ推論セッションを再利用する。"""
    ort = sys.modules["onnxruntime"]
    session_factory = Mock()
    monkeypatch.setattr(ort, "InferenceSession", session_factory, raising=False)
    monkeypatch.setattr(ort, "SessionOptions", Mock(), raising=False)
    tokenizer_factory = sys.modules["tokenizers"].Tokenizer.from_file
    s3_client = Mock(side_effect=AssertionError("判定モデルでS3の取得は不要"))
    monkeypatch.setattr("boto3.client", s3_client)
    monkeypatch.delenv("MODEL_BUCKET", raising=False)

    first_session, first_tokenizer = decision_worker.load()
    next_session, next_tokenizer = decision_worker.load()

    assert first_session is next_session is session_factory.return_value
    assert first_tokenizer is next_tokenizer is tokenizer_factory.return_value
    session_factory.assert_called_once()
    tokenizer_factory.assert_called_once()
    weights_path = Path(session_factory.call_args.args[0])
    tokenizer_path = Path(tokenizer_factory.call_args.args[0])
    assert weights_path.parent == tokenizer_path.parent == Path("/opt/models/decision")
    assert weights_path.name == "model.onnx" and tokenizer_path.name == "tokenizer.json"
    s3_client.assert_not_called()


@pytest.mark.parametrize(
    "role",
    [
        pytest.param(
            "tool", id="search", marks=pytest.mark.case_detail("検索語生成用の固定版の重みを再利用する")
        ),
        pytest.param(
            "generate",
            id="answer",
            marks=pytest.mark.case_detail("回答生成用の固定版の重みを再利用する"),
        ),
    ],
)
def test_generation_worker_reuses_downloaded_versioned_weights(workers, tmp_path, monkeypatch, role):
    """生成用の固定版の重みを一度取得し、メモリキャッシュを作り直した後も一時ファイルを再利用する。"""
    runtime = workers("model_runtime")
    filename = "model.gguf"
    manifest = {
        role: [
            {
                "name": filename,
                "revision": "fixture-commit",
                "file": filename,
                "repo": "example/generation-model",
            }
        ]
    }
    monkeypatch.setattr(runtime, "manifest", lambda: manifest)
    monkeypatch.setenv("MODEL_BUCKET", "fixture-models")
    monkeypatch.setattr(runtime, "Path", lambda base: tmp_path if base == "/tmp" else Path(base))
    storage = Mock()

    def download(bucket, key, target):
        assert bucket == "fixture-models"
        assert key == f"tsugite-chat-models/{role}/fixture-commit/{filename}"
        Path(target).write_bytes(b"GGUF fixture")

    storage.download_file.side_effect = download
    monkeypatch.setattr(runtime.boto3, "client", lambda service: storage)
    runtime.model_file.cache_clear()
    try:
        first = Path(runtime.model_file(role, filename))
        assert first.is_relative_to(tmp_path) and first.read_bytes() == b"GGUF fixture"
        runtime.model_file.cache_clear()
        assert Path(runtime.model_file(role, filename)) == first
        storage.download_file.assert_called_once()
    finally:
        runtime.model_file.cache_clear()
