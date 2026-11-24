# 利用者が確認できる上限・操作・通知を設定し、呼び出し結果と一覧を照合する。
import pytest

from tests.support.catalog import approved, headers


def test_lifetime_inheritance_and_reset(portal):
    """部署の有効期間上限をプロジェクトが継承し、個別上限を消すと上位の値に戻る。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    for key, kind, parent in (("lab", "department", ""), ("study", "project", "lab")):
        created = portal.put(
            f"/api/workspace/units/{key}", headers=admin, json={"kind": kind, "name": key, "parent": parent},
        )
        assert created.status_code == 200
        assigned = portal.put(
            "/api/workspace/memberships", headers=admin,
            json={"subject": subject, "unit_id": key, "leader": True},
        )
        assert assigned.status_code == 200
    for key, minutes in (("lab", 30), ("study", 10)):
        configured = portal.put(
            f"/api/credential-limits/units/{key}", headers=user, json={"max_minutes": minutes},
        )
        assert configured.status_code == 200
        assert configured.json()["max_minutes"] == minutes
    url = "/api/credential-limits/units/study"
    assert portal.get(url, headers=user).json()["inherited_minutes"] == 30
    options_url = "/api/credentials/options"
    assert portal.get(options_url, headers=user, params={"project": "study"}).json()["max_minutes"] == 10
    removed = portal.put(url, headers=user, json={"max_minutes": None})
    assert removed.status_code == 200
    assert removed.json()["max_minutes"] is None and removed.json()["inherited_minutes"] == 30
    options = portal.get(options_url, headers=user, params={"project": "study"}).json()
    assert options["may_manage"] and options["max_minutes"] == 30


def test_provider_changes_and_clears_individual_operations(portal):
    """提供者が一部の操作、全解除、継承を順に設定すると、商品詳細で本人に示す操作も切り替わる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, _ = approved(portal, owner, user)
    url = f"/api/apis/{asset_id}"
    policy_url = f"{url}/operation-policy"
    subject = portal.get("/api/me", headers=user).json()["subject"]
    policies = portal.get(policy_url, headers=owner).json()
    assert any(m["subject"] == subject for m in policies["members"])
    operations = policies["operations"]
    assert operations
    for selection in ([operations[0]], [], None):
        update = portal.put(policy_url, headers=owner, json={"subject": subject, "operations": selection})
        assert update.status_code == 200 and update.json()["operations"] == selection
        permissions = portal.get(policy_url, headers=owner).json()["permissions"]
        detail = portal.get(url, headers=user).json()
        if selection is None:
            assert subject not in permissions
        else:
            assert permissions[subject] == selection and detail["allowed_operations"] == selection


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(False, id="notify", marks=pytest.mark.case_detail("通知のみなら上限到達後も呼び出せて、通知は一回に限られる")),
        pytest.param(True, id="stop", marks=pytest.mark.case_detail("停止ありなら上限到達の次の呼び出しを止め、設定の更新で再開する")),
    ],
)
def test_alert_threshold_and_counter_reset(portal, stop):
    """到達時に一回だけ通知し、上限を変更すると次の呼び出しを新しい件数として集計する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    issued = portal.post(
        "/api/keys", headers=user,
        json={"name": "配送件数", "kind": "personal", "project": "finance", "api_ids": [asset_id]},
    )
    assert issued.status_code == 201
    caller = {**user, "X-API-Key": issued.json()["secret"]}
    targets = portal.get("/api/management-targets", headers=owner).json()
    assert any(
        t["asset_id"] == asset_id and t["project"] == "finance" and t["environment"] == "sandbox"
        for t in targets
    )
    rule = {
        "asset_id": asset_id, "project": "finance", "environment": "sandbox",
        "threshold": 1, "minutes": 1440, "stop": stop,
    }
    configured = portal.put("/api/alerts", headers=owner, json=rule)
    assert configured.status_code == 200

    def unread():
        return portal.get("/api/notifications/count", headers=user).json()["unread"]

    before = unread()
    call = portal.get(invoke_url, headers=caller)
    assert call.status_code == 200, (invoke_url, call.json())
    assert unread() == before + 1
    assert portal.get(invoke_url, headers=caller).status_code == (429 if stop else 200)
    assert unread() == before + 1
    reset = portal.put("/api/alerts", headers=owner, json={**rule, "threshold": 3})
    assert reset.status_code == 200
    listed = portal.get("/api/alerts", headers=owner).json()
    changed = next(item for item in listed if item["asset_id"] == asset_id)
    assert changed["threshold"] == 3 and changed["calls"] == 0
    call = portal.get(invoke_url, headers=caller)
    assert call.status_code == 200, (invoke_url, call.json())
