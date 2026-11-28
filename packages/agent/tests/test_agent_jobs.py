"""同じ受付番号の再送はワーカーを増やさず、本人が有効期間内に結果を取得できる。"""

import json
from io import BytesIO
from unittest.mock import Mock

import chat_jobs as jobs
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


def test_concurrent_submission_and_result_updates(monkeypatch):
    """重複した受付を抑止し、結果保存が競合した場合だけ先に書き込まれた結果を維持する。"""
    import pytest
    from botocore.exceptions import ClientError

    table = Mock()
    table.get_item.return_value = {}
    monkeypatch.setattr(jobs, "table", lambda: table)
    actor = Actor("利用者", frozenset(), frozenset(), False, False)
    for code in ("ConditionalCheckFailedException", "ServiceUnavailable"):
        error = ClientError({"Error": {"Code": code}}, "Write")
        table.put_item.side_effect = table.update_item.side_effect = error
        if code == "ConditionalCheckFailedException":
            with pytest.raises(jobs.RateLimited):
                jobs.submit("質問", actor, "request")
            jobs.store("key", {})
        else:
            with pytest.raises(ClientError, match="ServiceUnavailable"):
                jobs.submit("質問", actor, "request")
            with pytest.raises(ClientError, match="ServiceUnavailable"):
                jobs.store("key", {})
    assert table.put_item.call_count == table.update_item.call_count == 2


def test_worker_dispatch_failure_persists_retry_result(monkeypatch):
    """ワーカーの起動に失敗したときは失敗結果を保存し、受付側へ起動例外を返す。"""
    import pytest

    table, invoke = Mock(), Mock()
    table.get_item.return_value = {}
    invoke.invoke.side_effect = OSError("dispatch")
    monkeypatch.setattr(jobs, "table", lambda: table)
    monkeypatch.setattr(jobs, "lambda_client", lambda: invoke)
    monkeypatch.setenv("CHAT_WORKER", "worker")
    actor = Actor("利用者", frozenset(), frozenset(), False, False)
    with pytest.raises(OSError, match="dispatch"):
        jobs.submit("質問", actor, "request")
    update = table.update_item.call_args.kwargs
    assert update["Key"] == {"pk": jobs.key_for(actor.subject, "request")}
    assert json.loads(update["ExpressionAttributeValues"][":result"]) == jobs.FAILED


def test_unknown_job_and_worker_storage_failure(monkeypatch):
    """消えたジョブは処理せず、保存先の障害は要求識別子を記録して再送可能にする。"""
    import pytest

    table, emit = Mock(), Mock()
    table.get_item.side_effect = [{}, OSError("storage")]
    monkeypatch.setattr(jobs, "table", lambda: table)
    monkeypatch.setattr(jobs, "emit", emit)
    event = {"key": "absent", "request_id": "r-1"}
    assert jobs.handler(event, None) is None
    table.update_item.assert_not_called()
    with pytest.raises(OSError, match="storage"):
        jobs.handler(event, None)
    assert emit.call_args.kwargs["request_id"] == "r-1"
    assert emit.call_args.kwargs["reason"] == "OSError"
