# 初回パスワードの変更から認証アプリ登録まで、各応答のセッションを次の処理に渡す。
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest


def login(module):
    return module.PortalLogin({"client_id": "web", "identity_endpoint": "https://identity.example"})


def test_invitation_and_totp_setup(portal_module):
    """初回パスワードの変更から認証アプリ登録まで、各応答のセッションを次の処理に渡す。"""
    flow = login(portal_module("portal_auth"))
    flow.call = AsyncMock(
        side_effect=[
            {
                "ChallengeName": "NEW_PASSWORD_REQUIRED",
                "Session": "invite",
                "ChallengeParameters": {"USER_ID_FOR_SRP": "canonical"},
            },
            {"ChallengeName": "MFA_SETUP", "Session": "setup"},
            {"SecretCode": "MANUALKEY", "Session": "associated"},
            {"Status": "SUCCESS", "Session": "verified"},
            {"AuthenticationResult": {"AccessToken": "access", "IdToken": "id"}},
        ]
    )
    assert asyncio.run(flow.submit(username=" invited ", password=" temporary ")) is None
    assert flow.step == "new_password"
    assert asyncio.run(flow.submit(password=" replacement ")) is None
    assert (flow.step, flow.secret) == ("setup", "MANUALKEY")
    assert asyncio.run(flow.submit(code="001234")) == "access"
    assert flow.call.await_args_list == [
        call(
            "InitiateAuth",
            ClientId="web",
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "invited", "PASSWORD": " temporary "},
        ),
        call(
            "RespondToAuthChallenge",
            ClientId="web",
            Session="invite",
            ChallengeName="NEW_PASSWORD_REQUIRED",
            ChallengeResponses={"USERNAME": "canonical", "NEW_PASSWORD": " replacement "},
        ),
        call("AssociateSoftwareToken", Session="setup"),
        call("VerifySoftwareToken", Session="associated", UserCode="001234"),
        call(
            "RespondToAuthChallenge",
            ClientId="web",
            Session="verified",
            ChallengeName="MFA_SETUP",
            ChallengeResponses={"USERNAME": "canonical"},
        ),
    ]
    assert (flow.step, flow.secret, flow.session) == ("signin", None, None)


def test_returning_user_retries_mfa(portal_module):
    """登録済みの利用者は確認コードを間違えても同じ画面で再入力できる。"""
    module = portal_module("portal_auth")
    flow = login(module)
    flow.call = AsyncMock(
        side_effect=[
            {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "pending"},
            module.LoginError("CodeMismatchException"),
            {"AuthenticationResult": {"AccessToken": "ok"}},
        ]
    )
    assert asyncio.run(flow.submit(username="member", password="password")) is None
    with pytest.raises(ValueError, match="確認コードが一致しません"):
        asyncio.run(flow.submit(code="000000"))
    assert flow.step == "mfa"
    assert asyncio.run(flow.submit(code="000001")) == "ok"
    assert flow.call.await_args.kwargs["ChallengeResponses"] == {
        "USERNAME": "member",
        "SOFTWARE_TOKEN_MFA_CODE": "000001",
    }


def test_reset_returns_to_signin(portal_module):
    """再設定コードを受け取った利用者は新しいパスワードを設定してログイン画面に戻れる。"""
    flow = login(portal_module("portal_auth"))
    flow.reset("forgot")
    flow.call = AsyncMock(return_value={})
    asyncio.run(flow.submit(username="member"))
    assert flow.step == "confirm_reset"
    assert asyncio.run(flow.submit(password="new-password", code="001234")) is None
    assert flow.step == "signin"
    assert flow.call.await_args_list == [
        call("ForgotPassword", ClientId="web", Username="member"),
        call(
            "ConfirmForgotPassword",
            ClientId="web",
            Username="member",
            ConfirmationCode="001234",
            Password="new-password",
        ),
    ]


def test_credentials_sent_to_identity_service(portal_module, monkeypatch):
    """パスワードは認証サービスへのPOST本文だけで送信し、エラーは日本語で表示する。"""
    module = portal_module("portal_auth")
    fetch = AsyncMock(
        return_value=SimpleNamespace(
            ok=False,
            json=AsyncMock(
                return_value={"__type": "service#NotAuthorizedException", "message": "upstream detail"}
            ),
        )
    )
    monkeypatch.setattr(module, "pyfetch", fetch)
    flow = login(module)
    with pytest.raises(ValueError, match="入力内容を確認"):
        asyncio.run(flow.submit(username="member", password=" test "))
    args, kwargs = fetch.await_args
    assert args == ("https://identity.example",)
    assert kwargs["method"] == "POST" and kwargs["redirect"] == "error"
    assert kwargs["headers"]["X-Amz-Target"] == "AWSCognitoIdentityProviderService.InitiateAuth"
    assert json.loads(kwargs["body"])["AuthParameters"]["PASSWORD"] == " test "
