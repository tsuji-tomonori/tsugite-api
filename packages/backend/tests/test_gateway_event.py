"""権限を毎回照合し、取消後は同じトークンでも拒否する。"""

from api_auth.authorizer import handler

from tests.support.catalog import FORM, headers, invocation_headers, publish_asset


def test_gateway_authorizer_rechecks_each_invocation(portal, monkeypatch):
    """権限を毎回照合し、取消後は同じトークンでも拒否する"""
    monkeypatch.setenv("ORIGIN_SECRET", "test-origin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    key = portal.post("/api/apis", json=FORM, headers=owner).json()["id"]
    root = "/api/apis/" + key
    publish_asset(portal, root, owner)
    row = portal.post(
        root + "/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "棚卸"},
    ).json()
    call = invocation_headers(portal, user)
    incoming = {
        "headers": {"authorization": call["Authorization"], "x-tsugite-origin": "test-origin"},
        "rawPath": f"/api/invoke/{key}/sandbox/finance/items",
        "requestContext": {"requestId": "gateway-test"},
    }
    assert handler({**incoming, "headers": {"authorization": user["Authorization"]}}, None) == {
        "isAuthorized": False
    }
    assert handler(incoming, None) == {"isAuthorized": False}
    endpoint = "/api/requests/" + row["id"]
    approved = portal.post(
        endpoint,
        headers=owner,
        json={"revision": row["revision"], "reason": "確認", "action": "approve"},
    ).json()
    assert handler(incoming, None) == {
        "isAuthorized": True,
        "context": {"subject": "consumer", "project": "finance"},
    }
    for direct_headers in ({}, {"x-tsugite-origin": "incorrect"}):
        direct = {**incoming, "headers": {"authorization": call["Authorization"], **direct_headers}}
        assert handler(direct, None) == {"isAuthorized": False}
    assert handler(
        {
            **incoming,
            "requestContext": {"requestId": "wrong-env"},
            "rawPath": incoming["rawPath"].replace("sandbox", "production"),
        },
        None,
    ) == {"isAuthorized": False}
    assert (
        portal.post(
            endpoint,
            headers=owner,
            json={"revision": approved["revision"], "reason": "終了", "action": "revoke"},
        ).status_code
        == 200
    )
    assert handler({**incoming, "requestContext": {"requestId": "after-revoke"}}, None) == {
        "isAuthorized": False
    }
    logs = portal.get("/api/audit?action=invoke.denied", headers=user).json()
    assert len(logs) == 3 and all(e["action"] == "invoke.denied" for e in logs)


def test_stack_deletion_preserves_database():
    """スタック削除イベントでDBを削除しない"""
    from app.migrate import handler as migrate

    assert migrate({"RequestType": "Delete"}, None)["PhysicalResourceId"] == "tsugite-catalog-schema"


def test_gateway_scoped_key_authorizer(portal, monkeypatch):
    """API Gateway用の認可関数で、本人キー・別ユーザー・失効の判定を確認する"""
    from tests.support.catalog import approved

    monkeypatch.setenv("ORIGIN_SECRET", "origin")
    owner, user = (headers(portal, p) for p in ("provider", "consumer"))
    asset, _, path = approved(portal, owner, user)
    key = (
        portal.post(
            "/api/keys",
            headers=user,
            json={
                "project": "finance",
                "name": "ゲートウェイ試験",
                "kind": "personal",
                "api_ids": [asset],
            },
        )
        .raise_for_status()
        .json()
    )
    context = {
        "headers": {
            "authorization": user["Authorization"],
            "x-api-key": key["secret"],
            "x-tsugite-origin": "origin",
        },
        "rawPath": path,
        "requestContext": {"requestId": "key-test"},
    }
    assert handler(context, None)["isAuthorized"]
    assert not handler(
        {**context, "headers": {**context["headers"], "authorization": owner["Authorization"]}}, None
    )["isAuthorized"]
    assert not handler(
        {
            **context,
            "headers": {"authorization": "Bearer " + key["secret"], "x-tsugite-origin": "origin"},
        },
        None,
    )["isAuthorized"]
    portal.delete("/api/keys/" + key["id"], headers=user).raise_for_status()
    assert not handler(context, None)["isAuthorized"]
