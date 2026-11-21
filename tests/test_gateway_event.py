from app.authorizer import handler
from test_catalog import FORM, headers


def test_gateway_authorizer_rechecks_each_invocation(portal, monkeypatch):
    monkeypatch.setenv("ORIGIN_SECRET", "test-origin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    key = portal.post("/api/apis", json=FORM, headers=owner).json()["id"]
    root = "/api/apis/" + key
    portal.put(root + "/publication?published=true", headers=owner)
    row = portal.post(
        root + "/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "棚卸"},
    ).json()
    incoming = {
        "headers": {"authorization": user["Authorization"], "x-tsugite-origin": "test-origin"},
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
    assert handler(
        {**incoming, "rawPath": incoming["rawPath"].replace("sandbox", "production")}, None
    ) == {"isAuthorized": False}
    assert (
        portal.post(
            endpoint,
            headers=owner,
            json={"revision": approved["revision"], "reason": "終了", "action": "revoke"},
        ).status_code
        == 200
    )
    assert handler(incoming, None) == {"isAuthorized": False}
    logs = portal.get("/api/audit?request_id=gateway-test", headers=owner).json()
    assert len(logs) == 3 and all(e["action"] == "invoke.denied" for e in logs)


def test_stack_deletion_preserves_database():
    from app.migrate import handler as migrate

    assert migrate({"RequestType": "Delete"}, None)["PhysicalResourceId"] == "tsugite-catalog-schema"
