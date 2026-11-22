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
        {"issuer": "ignored", "iss": "https://other.invalid"},
        {"token_use": "id"},
        {"client_id": "other"},
        {"exp": 0},
        {"client_id": "batch", "scope": "openid"},
    ],
)
def test_invalid_token(signer, bad):
    with pytest.raises(HTTPException) as exc:
        auth.identify(signer(**bad))
    assert exc.value.status_code == 401


def test_people_and_machines(signer):
    human = auth.identify(signer())
    assert human.projects == {"finance"} and not human.machine
    machine = auth.identify(signer(client_id="batch", scope="hub/invoke"))
    assert machine.machine and machine.subject == "batch" and machine.projects == {"finance"}
    with pytest.raises(HTTPException) as exc:
        auth.human(machine)
    assert exc.value.status_code == 403
