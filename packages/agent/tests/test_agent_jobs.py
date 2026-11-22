import json
from io import BytesIO
from unittest.mock import Mock

from agent import jobs
from app.core.auth import Actor


def test_worker_dispatch_and_result_lifecycle(monkeypatch):
    """同じ受付番号の再送はワーカーを増やさず、本人が有効期間内に結果を取得できる。"""
    table = Mock()
    invoke = Mock()
    monkeypatch.setattr(jobs, "table", lambda: table)
    monkeypatch.setattr(jobs, "lambda_client", lambda: invoke)
    monkeypatch.setattr(jobs, "time", lambda: 100)
    monkeypatch.setenv("CHAT_WORKER", "worker")
    actor = Actor("利用者", frozenset(["project"]), frozenset(), False, False)
    key = jobs.key_for(actor.subject, "request")
    rows = {}
    table.get_item.side_effect = lambda Key, ConsistentRead: {"Item": rows.get(Key["pk"])}
    table.put_item.side_effect = lambda Item, **kwargs: rows.update({Item["pk"]: Item})
    jobs.submit("検索", actor, "request")
    jobs.submit("検索", actor, "request")
    invoke.invoke.assert_called_once()
    payload = json.loads(invoke.invoke.call_args.kwargs["Payload"])
    assert payload["key"] == key
    assert payload["actor"]["projects"] == ["project"]
    assert invoke.invoke.call_args.kwargs["InvocationType"] == "Event"
    assert jobs.status(actor.subject, "request") == {}
    assert jobs.status("別の利用者", "request") is None

    def answer(question, products, viewer, models):
        assert question == "検索" and viewer == actor
        return {"kind": "catalog", "keys": ["api"]}

    monkeypatch.setattr(jobs, "ask", answer)
    jobs.handler(payload, None)
    update = table.update_item.call_args.kwargs
    assert update["Key"] == {"pk": key}
    assert "attribute_not_exists(#result)" in update["ConditionExpression"]
    rows[key]["result"] = update["ExpressionAttributeValues"][":result"]
    assert jobs.status(actor.subject, "request") == {"kind": "catalog", "keys": ["api"]}
    jobs.handler(payload, None)
    table.update_item.assert_called_once()
    monkeypatch.setattr(jobs, "time", lambda: 100 + jobs.JOB_TTL)
    assert jobs.status(actor.subject, "request") is None


def test_worker_model_result_and_unavailable_model(monkeypatch):
    """モデルの辞書応答を返し、設定漏れ・関数エラー・壊れた応答では空の候補で処理を続ける。"""
    client = Mock()
    monkeypatch.setattr(jobs, "lambda_client", lambda: client)
    monkeypatch.delenv("CHAT_TOOL", raising=False)
    assert jobs.models("tool", {}) == {}
    client.invoke.assert_not_called()
    monkeypatch.setenv("CHAT_TOOL", "query-model")
    client.invoke.side_effect = [
        {"Payload": BytesIO(b'{"query":"api"}')},
        {"FunctionError": "Unhandled"},
        {"Payload": BytesIO(b"[]")},
        {"Payload": BytesIO(b"invalid")},
    ]
    assert jobs.models("tool", {"question": "検索"}) == {"query": "api"}
    assert client.invoke.call_args.kwargs["FunctionName"] == "query-model"
    assert json.loads(client.invoke.call_args.kwargs["Payload"]) == {"question": "検索"}
    for _ in range(3):
        assert jobs.models("tool", {}) == {}


def test_expired_job_returns_error_without_invoking_models(monkeypatch):
    """期限ちょうどのジョブは失敗として返し、遅れて届いたワーカーが上書きしない。"""
    table = Mock()
    table.get_item.return_value = {"Item": {"deadline": 100, "expires": 200}}
    monkeypatch.setattr(jobs, "table", lambda: table)
    monkeypatch.setattr(jobs, "time", lambda: 100)
    assert jobs.status("subject", "request") == jobs.FAILED
    jobs.handler({"key": jobs.key_for("subject", "request")}, None)
    table.update_item.assert_not_called()
