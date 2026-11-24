from time import time
from types import SimpleNamespace

import jwt
import pytest
from app.core import auth
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException


@pytest.fixture
def signer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "local_demo", lambda: False)
    monkeypatch.setattr(
        auth,
        "settings",
        lambda: {
            "issuer": "https://test.invalid/pool",
            "portal_client": "ui",
            "machine_projects": [{"client": "batch", "project": "finance"}],
        },
    )
    monkeypatch.setattr(
        auth,
        "keyset",
        lambda issuer: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )

    def issue(**overrides):
        claims = {
            "iss": "https://test.invalid/pool",
            "sub": "user-id",
            "exp": int(time()) + 120,
            "client_id": "ui",
            "token_use": "access",
            "cognito:groups": ["use-finance"],
        }
        return jwt.encode({**claims, **overrides}, key, algorithm="RS256")

    return issue


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            {"issuer": "ignored", "iss": "https://other.invalid"},
            id="bad0",
            marks=pytest.mark.case_detail("発行元が設定値と異なる"),
        ),
        pytest.param(
            {"token_use": "id"}, id="bad1", marks=pytest.mark.case_detail("IDトークンを送った場合")
        ),
        pytest.param(
            {"client_id": "other"},
            id="bad2",
            marks=pytest.mark.case_detail("未登録クライアントから送信"),
        ),
        pytest.param({"exp": 0}, id="bad3", marks=pytest.mark.case_detail("有効期限を過ぎている")),
        pytest.param(
            {"client_id": "batch", "scope": "openid"},
            id="bad4",
            marks=pytest.mark.case_detail("システム用トークンに呼び出しスコープがない"),
        ),
    ],
)
def test_invalid_token(signer, bad):
    """条件を満たさないアクセストークンを401で拒否する"""
    with pytest.raises(HTTPException) as exc:
        auth.identify(signer(**bad))
    assert exc.value.status_code == 401


def test_people_and_machines(signer):
    """人とシステムを識別し、システムのポータル利用を拒否する"""
    human = auth.identify(signer())
    assert human.projects == {"finance"} and not human.machine
    machine = auth.identify(signer(client_id="batch", scope="hub/invoke"))
    assert machine.machine and machine.subject == "batch" and machine.projects == {"finance"}
    with pytest.raises(HTTPException) as exc:
        auth.human(machine)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "direct_headers",
    [
        pytest.param({}, id="missing", marks=pytest.mark.case_detail("入口ヘッダーがない場合は403")),
        pytest.param(
            {"x-tsugite-origin": "incorrect"},
            id="incorrect",
            marks=pytest.mark.case_detail("入口ヘッダーが一致しない場合は403"),
        ),
    ],
)
def test_portal_origin_with_valid_access_token(portal, signer, monkeypatch, direct_headers):
    """署名が有効な同じ利用者トークンで、正規入口の本人照会は成功し、直接の本人照会は403になる。"""
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "portal-api")
    monkeypatch.setenv("ORIGIN_SECRET", "fixture-origin")
    token = {"Authorization": "Bearer " + signer()}
    allowed = portal.get("/api/me", headers={**token, "x-tsugite-origin": "fixture-origin"})
    assert allowed.status_code == 200 and allowed.json()["subject"] == "user-id"
    denied = portal.get("/api/me", headers={**token, **direct_headers})
    assert denied.status_code == 403 and denied.json() == {"detail": "入口を確認してください"}
