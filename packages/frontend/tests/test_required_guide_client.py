"""要件「運用ログから対象と復旧作業を確認できる」に基づき、ポータルの通信失敗と画面ログを検証する。"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from test_required_guide import PortalModule


@pytest.mark.parametrize(
    ("status", "level", "detail"),
    [
        pytest.param(
            422,
            "WARN",
            "入力内容を確認してください",
            id="validation",
            marks=pytest.mark.case_detail("入力不備は内容を伝え、WARNの画面ログを記録する。"),
        ),
        pytest.param(
            401,
            "WARN",
            "ログインが必要です",
            id="expired",
            marks=pytest.mark.case_detail("期限切れのログインは通知し、使えない資格情報を破棄する。"),
        ),
        pytest.param(
            503,
            "ERROR",
            "一時的に接続できません",
            id="unavailable",
            marks=pytest.mark.case_detail("一時障害は対象APIとHTTP状態をERRORの画面ログに記録する。"),
        ),
    ],
)
def test_service_error_with_no_trace_id_is_visible_to_the_operator(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    level: str,
    detail: str,
) -> None:
    """リクエストIDを得られないAPIエラーは画面に理由を返し、対象と分類をブラウザーに記録する。"""
    client = portal_module("apis.client")
    window = Mock()
    window.location.hash = "#/metrics"
    store = Mock()
    store.getItem.return_value = "example-portal-session"
    monkeypatch.setattr(client, "window", window)
    monkeypatch.setattr(client, "store", store)
    response = Mock(status=status, ok=False, headers={}, json=AsyncMock(return_value={"detail": detail}))
    fetch = AsyncMock(return_value=response)
    monkeypatch.setattr(client, "pyfetch", fetch)
    with pytest.raises(client.ResponseError, match=detail):
        asyncio.run(client.api("/metrics"))
    writer = window.console.warn if level == "WARN" else window.console.error
    writer.assert_called_once()
    record = json.loads(writer.call_args.args[0])
    assert record["route"] == "/api/metrics" and record["method"] == "GET" and record["status"] == status
    assert record["level"] == level and record["source"] == "browser"
    assert datetime.fromisoformat(record["at"]).utcoffset() == timedelta(0)
    assert record["request_id"] is None and record["reason"]
    assert "example-portal-session" not in writer.call_args.args[0]
    if status == 401:
        store.removeItem.assert_called_once()


def test_ui_report_can_be_correlated_to_an_api_response(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """画面で起きた処理エラーは、対象API・画面の処理・指定したリクエストIDで照合できる。"""
    client = portal_module("apis.client")
    window = Mock()
    window.location.hash = "#/metrics"
    monkeypatch.setattr(client, "window", window)
    client.report(
        RuntimeError("応答を読み取れません"),
        "利用状況を表示",
        route="/api/metrics",
        method="GET",
        status=503,
        request_id="demo-metrics-trace",
    )
    window.console.error.assert_called_once()
    entry = json.loads(window.console.error.call_args.args[0])
    assert entry["request_id"] == "demo-metrics-trace"
    assert entry["route"] == "/api/metrics" and entry["operation"] == "利用状況を表示"
    assert entry["level"] == "ERROR"


def test_non_json_failure_retains_http_status(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """接続先の失敗応答がJSONでなくても、HTTP状態を含む案内を返す。"""
    client = portal_module("apis.client")
    monkeypatch.setattr(client, "window", Mock())
    store = Mock()
    store.getItem.return_value = None
    monkeypatch.setattr(client, "store", store)
    response = Mock(
        status=503, ok=False, headers={}, json=AsyncMock(side_effect=ValueError("応答形式不明"))
    )
    monkeypatch.setattr(client, "pyfetch", AsyncMock(return_value=response))
    with pytest.raises(client.ResponseError, match="503"):
        asyncio.run(client.api("/metrics"))


@pytest.mark.parametrize(
    ("status", "response", "message"),
    [
        pytest.param(
            200,
            {"Status": "SUCCESS"},
            "",
            id="confirmed",
            marks=pytest.mark.case_detail("確認コードを認証APIへ直接送り成功を受け取る。"),
        ),
        pytest.param(
            400,
            {"__type": "CodeMismatchException"},
            "確認コード",
            id="mismatched-code",
            marks=pytest.mark.case_detail("確認コードが違うときは新しいコードの入力を日本語で促す。"),
        ),
        pytest.param(
            503,
            {"message": "temporarily unavailable"},
            "ログイン",
            id="unavailable",
            marks=pytest.mark.case_detail("認証サービスの一時障害は日本語で再ログインを案内する。"),
        ),
    ],
)
def test_user_pool_directly_receives_the_authenticator_code(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    response: dict[str, str],
    message: str,
) -> None:
    """認証コードはユーザープールに直接POSTし、失敗時には次の操作を日本語で案内する。"""
    auth = portal_module("apis.portal_auth")
    endpoint = "https://identity.example.test"
    wire = AsyncMock(
        return_value=Mock(status=status, ok=status == 200, json=AsyncMock(return_value=response))
    )
    monkeypatch.setattr(auth, "pyfetch", wire)
    request = auth.request(endpoint, "VerifySoftwareToken", UserCode="123456")
    if message:
        with pytest.raises(auth.LoginError, match=message):
            asyncio.run(request)
    else:
        assert asyncio.run(request) == response
    wire.assert_awaited_once()
    assert wire.await_args is not None
    assert wire.await_args.args == (endpoint,)
    assert wire.await_args.kwargs["method"] == "POST"
    assert json.loads(wire.await_args.kwargs["body"]) == {"UserCode": "123456"}
