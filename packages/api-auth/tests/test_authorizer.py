"""API Gatewayのイベントに対する許可・拒否と監査記録を確認する。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from api_auth import authorizer
from fastapi import HTTPException


@pytest.fixture
def incoming(monkeypatch):
    monkeypatch.setenv("ORIGIN_SECRET", "origin")
    return {
        "headers": {"x-tsugite-origin": "origin", "authorization": "Bearer trial"},
        "requestContext": {"requestId": "req", "http": {"method": "GET"}},
        "rawPath": "/api/invoke/catalog/sandbox/project/items",
    }


@pytest.fixture
def policy(monkeypatch):
    db = MagicMock()
    session = MagicMock()
    session.return_value.__enter__.return_value = db
    monkeypatch.setattr(authorizer, "engine", Mock())
    monkeypatch.setattr(authorizer, "Session", session)
    actor = SimpleNamespace(subject="reader", key_id="key", projects={"project"})
    asset = SimpleNamespace(id="asset", owner="owner", spec='{"paths":{"/items":{"get":{}}}}')
    for name, value in {
        "invocation_actor": actor,
        "retired_units": {},
        "invocation_asset": asset,
        "authorize": None,
        "check_operation": None,
        "attribute": None,
        "emit": None,
    }.items():
        monkeypatch.setattr(authorizer, name, Mock(return_value=value))
    return db, actor, asset


def test_allow_operation(incoming, policy):
    """呼び出し元と操作を検査した後に利用者とプロジェクトをAPI Gatewayへ返す。"""
    db, actor, asset = policy
    assert authorizer.handler(incoming, None) == {
        "isAuthorized": True,
        "context": {"subject": "reader", "project": "project"},
    }
    authorizer.check_operation.assert_called_once_with(db, asset, actor, "GET /items", "project")


def test_reject_invalid_event_before_database(incoming, monkeypatch):
    """入口の秘密値、認証方式、パスのいずれかが不正ならDBに接続せず拒否する。"""
    engine = Mock()
    monkeypatch.setattr(authorizer, "engine", engine)
    for change in (
        {"headers": {}},
        {"headers": {"x-tsugite-origin": "origin", "authorization": "Basic trial"}},
        {"rawPath": "/api/invoke/catalog"},
        {"rawPath": "/api/other/catalog/sandbox/project/items"},
    ):
        assert authorizer.handler({**incoming, **change}, None) == {"isAuthorized": False}
    engine.assert_not_called()


def test_identity_errors(incoming, policy):
    """認証情報の拒否と認証サービスの障害を区別してログに記録する。"""
    for status, reason in ((401, "authorization_denied"), (503, "authentication_service_error")):
        authorizer.invocation_actor.side_effect = HTTPException(status)
        assert authorizer.handler(incoming, None) == {"isAuthorized": False}
        assert authorizer.emit.call_args.kwargs["reason"] == reason


def test_denied_operation_is_audited(incoming, policy):
    """操作が拒否されたときは監査イベントとアクセスログを同じ要求IDで保存する。"""
    db, actor, _ = policy
    authorizer.check_operation.side_effect = HTTPException(403)
    assert authorizer.handler(incoming, None) == {"isAuthorized": False}
    event, access = [call.args[0] for call in db.add.call_args_list]
    assert event.action == "invoke.denied" and event.request_id == access.request_id == "req"
    assert access.operation == "/items" and access.status == 403
    authorizer.attribute.assert_called_once_with(db, "req", actor, "project")
    db.commit.assert_called_once_with()


def test_asset_lookup_errors(incoming, policy):
    """商品を特定できない障害は原因をログに残し、商品にひも付く監査行は作らない。"""
    db, _, _ = policy
    for error, reason in (
        (HTTPException(503), "authorization_service_error"),
        (authorizer.OperationalRepair("invalid_spec", "repair_spec"), "invalid_spec"),
    ):
        authorizer.invocation_asset.side_effect = error
        assert authorizer.handler(incoming, None) == {"isAuthorized": False}
        assert authorizer.emit.call_args.kwargs["reason"] == reason
    db.add.assert_not_called()


def test_invocation_without_operation(incoming, policy):
    """操作パスのない許可済み要求は商品単位の判定結果を返す。"""
    incoming["rawPath"] = "/api/invoke/catalog/sandbox/project"
    assert authorizer.handler(incoming, None)["isAuthorized"]
    authorizer.check_operation.assert_not_called()


def test_unexpected_error_is_reported(incoming, policy):
    """予期しない障害は種類を記録し、Lambdaの失敗として呼び出し元に返す。"""
    authorizer.invocation_actor.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        authorizer.handler(incoming, None)
    assert authorizer.emit.call_args.kwargs["reason"] == "RuntimeError"
