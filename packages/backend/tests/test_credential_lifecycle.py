# 提供者・部署・プロジェクトの上限、更新と失効の秒境界、発行後の上限短縮を確認する。
from time import time

from app.core import credential_policy

from tests.support.catalog import approved, headers


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_nested_token_lifetime(portal, monkeypatch):
    """提供者・部署・プロジェクトの上限、更新と失効の秒境界、発行後の上限短縮を確認する"""
    owner, user, admin = (headers(portal, role) for role in ("provider", "consumer", "admin"))
    asset, _, path = approved(portal, owner, user)
    now = int(time())
    delta = 0
    monkeypatch.setattr(credential_policy, "clock", lambda: now + delta)
    for name, kind, parent in (
        ("org", "department", ""),
        ("team", "department", "org"),
        ("finance", "project", "team"),
    ):
        portal.put(
            "/api/workspace/units/" + name,
            headers=admin,
            json={"kind": kind, "name": name, "parent": parent},
        ).raise_for_status()

    def limit(resource, value, actor):
        return portal.put(
            "/api/credential-limits/" + resource, headers=actor, json={"max_minutes": value}
        )

    limit("apis/" + asset, 45, owner).raise_for_status()
    for name, inherited, chosen in (("org", 45, 30), ("team", 30, 25), ("finance", 25, 20)):
        assert limit("units/" + name, inherited + 1, admin).status_code == 422
        assert (
            limit("units/" + name, chosen, admin).raise_for_status().json()["inherited_minutes"]
            == inherited
        )
    assert limit("units/finance", 12, user).status_code == 403
    data = {
        "name": "短期",
        "mode": "bearer",
        "kind": "personal",
        "project": "finance",
        "api_ids": [asset],
    }
    assert (
        portal.post("/api/credentials", headers=user, json={**data, "ttl_minutes": 21}).status_code
        == 422
    )
    first = (
        portal.post(
            "/api/credentials", headers=user, json={**data, "ttl_minutes": 10, "refresh_minutes": 5}
        )
        .raise_for_status()
        .json()
    )
    endpoint = "/api/credentials/" + first["id"] + "/token"
    original = bearer(first["access_token"])
    assert portal.get(path, headers=original).is_success
    assert portal.post(endpoint, headers=original).status_code == 401
    assert portal.get(path, headers={**user, "X-Tsugite-Key-Id": first["id"]}).status_code == 401
    delta = 299
    before = portal.post(endpoint, headers=user).raise_for_status().json()
    assert before["access_token"] == first["access_token"] and before["refresh_after"] == 1
    delta = 300
    second = portal.post(endpoint, headers=user).raise_for_status().json()
    assert second["access_token"] != first["access_token"] and second["expires_in"] == 600
    delta = 599
    assert portal.get(path, headers=original).is_success
    delta = 600
    assert portal.get(path, headers=original).status_code == 401
    assert portal.get(path, headers=bearer(second["access_token"])).is_success
    limit("apis/" + asset, 2, owner).raise_for_status()
    assert portal.get(path, headers=bearer(second["access_token"])).status_code == 401
    short = portal.post(endpoint, headers=user).raise_for_status().json()
    assert short["expires_in"] == 120 and short["refresh_after"] == 120
    assert portal.get(path, headers=bearer(short["access_token"])).is_success


def test_persistent_system_and_legacy_expiry(portal, monkeypatch):
    """60日後もシステム資格で再発行でき、古いアクセストークン・従来キーは失効する"""
    owner, user, admin = (headers(portal, role) for role in ("provider", "consumer", "admin"))
    asset, _, path = approved(portal, owner, user)
    start = int(time())
    delta = 0
    monkeypatch.setattr(credential_policy, "clock", lambda: start + delta)
    base = {"name": "夜間集計", "kind": "shared", "project": "finance", "api_ids": [asset]}
    legacy = portal.post("/api/keys", headers=user, json=base).raise_for_status().json()
    credential = {**base, "mode": "system", "ttl_minutes": 4}
    assert portal.post("/api/credentials", headers=user, json=credential).status_code == 403
    portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"unit_id": "finance", "subject": "consumer", "leader": True},
    ).raise_for_status()
    client = portal.post("/api/credentials", headers=user, json=credential).raise_for_status().json()
    proof = {k: client[k] for k in ("client_id", "client_secret")}

    def exchange():
        return portal.post("/api/auth/token", json=proof).raise_for_status().json()

    token = exchange()
    assert token["refresh_after"] == 180
    assert portal.get(path, headers=bearer(token["access_token"])).is_success
    assert portal.get(path, headers=bearer(client["client_secret"])).status_code == 401
    assert portal.get(path, headers=bearer(legacy["secret"])).is_success
    delta = 3600
    assert portal.get(path, headers=bearer(legacy["secret"])).status_code == 401
    assert portal.get(path, headers={**user, "X-Tsugite-Key-Id": legacy["id"]}).status_code == 401
    delta = 60 * 86400
    assert portal.get(path, headers=bearer(token["access_token"])).status_code == 401
    new = exchange()
    assert new["expires_in"] == 240 and new["access_token"] != token["access_token"]
    assert portal.get(path, headers=bearer(new["access_token"])).is_success


def test_interactive_exchange_requires_registered_credential(portal):
    """本人の認証情報との交換だけを許可し、失効・他人の認証情報・ログイン単独の実行を拒否する。"""
    from app.apis.governance.credentials import ACCESS_TOKEN_TYPE, TOKEN_EXCHANGE

    owner, user = (headers(portal, who) for who in ("provider", "consumer"))
    asset, _, path = approved(portal, owner, user)
    assert portal.get(path, headers=user).status_code == 403
    key = (
        portal.post(
            "/api/credentials",
            headers=user,
            json={
                "name": "ポータル試行",
                "project": "finance",
                "kind": "personal",
                "mode": "app",
                "api_ids": [asset],
            },
        )
        .raise_for_status()
        .json()
    )
    endpoint = f"/api/credentials/{key['id']}/token-exchange"
    data = {
        "grant_type": TOKEN_EXCHANGE,
        "subject_token_type": ACCESS_TOKEN_TYPE,
        "subject_token": user["Authorization"].split()[1],
    }
    assert portal.post(endpoint, data={**data, "grant_type": "unknown"}).status_code == 400
    assert (
        portal.post(
            endpoint, data={**data, "subject_token": owner["Authorization"].split()[1]}
        ).status_code
        == 403
    )
    issued = portal.post(endpoint, data=data).raise_for_status()
    assert issued.headers["cache-control"] == "no-store"
    assert issued.json()["issued_token_type"] == ACCESS_TOKEN_TYPE
    token = bearer(issued.json()["access_token"])
    assert portal.get(path, headers=token).is_success
    portal.delete("/api/keys/" + key["id"], headers=user).raise_for_status()
    assert portal.post(endpoint, data=data).status_code == 401
    assert portal.get(path, headers=token).status_code == 401
