import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.core.diagnostics import asset_object, exported_invocation, invocation_details, logger
from app.core.request_logs import install_request_logs
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def logged_api(monkeypatch):
    app = FastAPI()
    install_request_logs(app)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    sink = Mock()
    monkeypatch.setattr(logger, "handlers", [sink])
    sink.level = 0

    @app.get("/api/apis/{key}")
    async def detail(key: str, request: Request, case: int = 0):
        request.state.actor_id = "actor-1"
        if case == 1:
            raise HTTPException(403, "private message")
        if case == 2:
            raise RuntimeError("private message")
        if case == 3:
            asset_object(SimpleNamespace(id=key, spec="private message"), "spec")
        return {"ok": True}

    async def get(path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path, **kwargs)

    return get, sink


def last(sink):
    assert sink.handle.call_count == 1
    return json.loads(sink.handle.call_args.args[0].getMessage())


@pytest.mark.parametrize(
    ("case", "status", "level"),
    [
        pytest.param(0, 200, "INFO", marks=pytest.mark.case_detail("正常に応答した呼び出しを記録する")),
        pytest.param(
            1, 403, "WARN", marks=pytest.mark.case_detail("権限不足の呼び出しを利用者起因に分類する")
        ),
        pytest.param(
            2, 500, "ERROR", marks=pytest.mark.case_detail("未処理例外をサーバー障害に分類する")
        ),
        pytest.param(
            3,
            503,
            "CRITICAL",
            marks=pytest.mark.case_detail("保存仕様が壊れたときにデータ修正の手順を残す"),
        ),
        pytest.param(
            "bad",
            422,
            "WARN",
            marks=pytest.mark.case_detail("入力値の型が違うときに利用者起因に分類する"),
        ),
    ],
)
def test_http_log(logged_api, case, status, level):
    """HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。"""
    api, sink = logged_api
    response = asyncio.run(
        api(
            "/api/apis/asset-1",
            params={"case": case, "password": "private message"},
            headers={"Authorization": "Bearer private message", "X-Tsugite-Screen": "api"},
        )
    )
    entry = last(sink)
    assert entry["status"] == response.status_code == status
    assert entry["level"] == level
    assert entry["asset_id"] == "asset-1" and entry["route"] == "/api/apis/{key}"
    assert entry["screen"] == "api" and entry["method"] == "GET"
    assert entry["actor_id"] == (None if status == 422 else "actor-1")
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["at"].endswith("+00:00")
    assert "private message" not in json.dumps(entry)
    if level == "CRITICAL":
        assert entry["reason"] == "invalid_asset_spec"
        assert all(word in entry["operator_action"] for word in ("assets", "asset_id", "spec", "復元"))
        assert "assets" not in response.text
    else:
        assert entry["operator_action"] is None


def test_origin_denial(logged_api, monkeypatch):
    """入口で拒否しても追跡IDを返し、未検証の利用者や画面を記録しない。"""
    api, sink = logged_api
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "api")
    monkeypatch.setenv("ORIGIN_SECRET", "origin-secret")
    response = asyncio.run(api("/api/apis/asset-1", headers={"X-Tsugite-Screen": "private message"}))
    entry = last(sink)
    assert entry["level"] == "WARN" and entry["reason"] == "origin_denied"
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["actor_id"] is None and entry["screen"] is None
    assert entry["route"] == "/api/apis/{key}" and entry["asset_id"] == "asset-1"


def test_export_preserves_repair():
    """履歴の出力時にも記録時点の復旧手順を保ち、旧形式の行も読み出せる。"""
    row = SimpleNamespace(
        actor="operator",
        status=503,
        diagnostics=invocation_details(
            "api", "api", 503, reason="invalid_asset_spec", action="assets.specを復元する"
        ),
    )
    data = {"at": "2026-11-22T00:00:00+00:00", "asset_id": "asset-1", "status": 503}
    event = exported_invocation(row, data)
    assert event["level"] == "CRITICAL" and event["operator_action"] == "assets.specを復元する"
    assert event["screen"] == "api" and event["at"] == data["at"] and event["actor_id"] == "operator"
    row.diagnostics = None
    historical = exported_invocation(row, data)
    assert historical["level"] == "ERROR" and historical["operator_action"] is None


def test_member_partial_deletion(monkeypatch):
    """ポータル停止後のCognito障害では、操作した管理者と対象利用者を分けて復旧方法を記録する。"""
    from app.apis.governance import members
    from app.core.auth import Actor, demo_token
    from botocore.exceptions import ClientError
    from tsugite_db.models import Member

    app = FastAPI()
    install_request_logs(app)
    sink = Mock(level=0)
    monkeypatch.setattr(logger, "handlers", [sink])
    monkeypatch.setenv("TSUGITE_DEMO", "1")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setattr(members, "local_demo", lambda: False)
    monkeypatch.setattr(members, "pool", lambda: "pool")
    identity = Mock()
    identity.admin_get_user.return_value = {"UserAttributes": [{"Name": "sub", "Value": "target-user"}]}
    identity.admin_delete_user.side_effect = ClientError(
        {"Error": {"Code": "InternalErrorException"}}, "Delete"
    )
    monkeypatch.setattr(members.boto3, "client", lambda _: identity)
    row = Member(subject="target-user", username="private@example.test", deleted=False)
    db = Mock()
    db.get.return_value = row

    @app.delete("/api/members/{subject}")
    async def remove(subject: str, request: Request):
        from app.core.auth import identify

        actor: Actor = identify(request.headers["authorization"].removeprefix("Bearer "))
        request.state.actor_id = actor.subject
        return members.remove_member(subject, row.username, request, actor, db)

    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.delete(
                "/api/members/target-user",
                headers={
                    "Authorization": "Bearer " + demo_token("admin"),
                    "X-Tsugite-Screen": "members",
                },
            )

    response = asyncio.run(run())
    assert row.deleted and response.status_code == 503
    entry = last(sink)
    assert (entry["level"], entry["actor_id"], entry["target_subject_id"]) == (
        "CRITICAL",
        "admin",
        "target-user",
    )
    assert entry["screen"] == "members" and "Cognito" in entry["operator_action"]
    assert row.username not in str(entry)


def test_model_worker_error_has_request_context(monkeypatch):
    """モデル呼び出しの失敗を元のAPI・画面・利用者に結び付け、質問本文を記録しない。"""
    from agent import jobs

    sink = Mock(level=0)
    monkeypatch.setattr(logger, "handlers", [sink])
    monkeypatch.setenv("CHAT_DECISION", "model")
    client = Mock()
    client.invoke.return_value = {"FunctionError": "Unhandled"}
    monkeypatch.setattr(jobs, "lambda_client", lambda: client)
    assert (
        jobs.models(
            "decision",
            {"texts": ["private message"]},
            screen="home",
            request_id="api-request",
            actor_id="user-1",
        )
        == {}
    )
    entry = last(sink)
    assert (entry["level"], entry["route"], entry["operation"]) == ("ERROR", "/api/chat", "decision")
    assert (entry["request_id"], entry["actor_id"], entry["screen"]) == ("api-request", "user-1", "home")
    assert "private message" not in str(entry)


def test_packaged_model_reports_weight_repair(tmp_path, monkeypatch, capsys):
    """モデルにも同じJSON形式を同梱し、重み不一致時は復元作業を記録する。"""
    import importlib.util
    from pathlib import Path

    from tools.packaging import build_chat

    monkeypatch.setattr(build_chat, "BUILD", tmp_path)
    build_chat.stage()
    for package in (tmp_path / "chat-decision", tmp_path / "chat-llm"):
        assert (package / "log_record.py").read_bytes() == (
            Path(__file__).resolve().parents[1] / "src/app/core/log_record.py"
        ).read_bytes()
    package = tmp_path / "chat-decision"
    monkeypatch.syspath_prepend(str(package))
    spec = importlib.util.spec_from_file_location("model_runtime", package / "runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    monkeypatch.setenv("MODEL_ROLE", "decision")

    @runtime.logged_model
    def predict(event, context):
        raise runtime.WeightMismatch("private message")

    with pytest.raises(runtime.WeightMismatch, match="private message"):
        predict({"log_context": {"actor_id": "actor", "request_id": "trace", "screen": "home"}}, None)
    entry = json.loads(capsys.readouterr().out)
    assert entry["level"] == "CRITICAL" and entry["source"] == "model"
    assert entry["operation"] == "decision" and "S3" in entry["operator_action"]
    assert entry["actor_id"] == "actor" and entry["request_id"] == "trace"
    assert "private message" not in str(entry)
