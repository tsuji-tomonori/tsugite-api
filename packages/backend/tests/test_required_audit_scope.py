# 組織改編の前後に発生した同じ商品の実行を、担当部署の監査と集計から照合する。
import json

from tests.support.catalog import approved, headers


def test_department_audit_uses_hierarchy_at_call_time(portal):
    """管轄部署の変更前後に呼び出すと、各部署のリーダーは実行時点で配下にあった記録を取得できる。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    owner = headers(portal, "provider")
    asset_id, _, invoke_url = approved(portal, owner, user)
    departments = ["former-office", "next-office"]
    for department in departments:
        assert (
            portal.put(
                f"/api/workspace/units/{department}",
                headers=admin,
                json={"kind": "department", "name": department},
            ).status_code
            == 200
        )
        subject = portal.get("/api/me", headers=owner).json()["subject"]
        assert (
            portal.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"unit_id": department, "subject": subject, "leader": True},
            ).status_code
            == 200
        )
    credential = portal.post(
        "/api/credentials",
        headers=user,
        json={
            "kind": "personal",
            "mode": "bearer",
            "project": "finance",
            "name": "監査対象",
            "api_ids": [asset_id],
        },
    )
    assert credential.status_code == 201
    caller = {"Authorization": f"Bearer {credential.json()['access_token']}"}
    request_ids = []
    for department in departments:
        moved = portal.put(
            "/api/workspace/units/finance",
            headers=admin,
            json={"kind": "project", "name": "経理", "parent": department},
        )
        assert moved.status_code == 200
        response = portal.get(invoke_url, headers=caller)
        assert response.status_code == 200
        request_ids.append(response.headers["x-request-id"])
    for department, request_id in zip(departments, request_ids, strict=True):
        scope = {"unit": department, "scope": "audit"}
        listed = portal.get("/api/access-logs", headers=owner, params={**scope, "asset_id": asset_id})
        assert listed.status_code == 200
        assert [row["request_id"] for row in listed.json()] == [request_id]
        dimensions = portal.get("/api/access-logs/dimensions", headers=owner, params=scope)
        assert dimensions.status_code == 200
        assert any(
            row["asset_id"] == asset_id and row["project"] == "finance" for row in dimensions.json()
        )
        detail = portal.get(
            "/api/access-logs/detail", headers=owner, params={**scope, "request_id": request_id}
        )
        assert detail.status_code == 200
        entry = detail.json()
        assert (
            entry["request_id"] == request_id
            and entry["status"] == 200
            and entry["key_id"] == credential.json()["id"]
        )
        exported = portal.get(
            "/api/access-logs/download", headers=owner, params={**scope, "request_id": request_id}
        )
        assert exported.status_code == 200
        assert [json.loads(line)["request_id"] for line in exported.text.splitlines()] == [request_id]
    query = {
        "minutes": 15,
        "project": "finance",
        "environment": "sandbox",
        "asset_id": asset_id,
        "status": 200,
    }
    metrics = portal.get("/api/metrics", headers=user, params=query)
    assert metrics.status_code == 200 and metrics.json()["minutes"] == 15
    assert sum(point["calls"] for point in metrics.json()["points"]) == 2
