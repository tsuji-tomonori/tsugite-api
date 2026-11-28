# 公開申請と利用申請の承認者をAPI経由で検証する。
import pytest

from tests.support.catalog import FORM, headers, publish_asset
from tests.support.quint import histories


def member(portal, admin, name):
    email = name + "@example.test"
    row = (
        portal.post(
            "/api/members",
            headers=admin,
            json={
                "email": email,
                "full_name": "登録 太郎",
                "project": "supply",
            },
        )
        .raise_for_status()
        .json()
    )
    return row["subject"], headers(portal, email)


@pytest.mark.parametrize("states", histories("publication"))
def test_publication_review(states, portal):
    """一般メンバーが申請し、指定プロジェクトのリーダーと管理者が順に承認すると公開される。"""
    admin = headers(portal, "admin")
    subject, applicant = member(portal, admin, "author")
    leader, lead = member(portal, admin, "lead")
    portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": leader, "unit_id": "supply", "leader": True},
    ).raise_for_status()
    rules = {"guidelines": "接続仕様を確認", "steps": ["unit/supply", "admin"]}
    policy = "/api/publication-policy"
    assert portal.put(policy, headers=applicant, json=rules).status_code == 403
    assert portal.get(policy, headers=applicant).json()["steps"] == ["admin"]
    assert portal.put(policy, headers=admin, json=rules).raise_for_status().json() == rules
    assert portal.put(policy, headers=admin, json={"steps": []}).status_code == 422
    assert portal.put(policy, headers=admin, json={"steps": ["unit/missing"]}).status_code == 422
    row = (
        portal.post("/api/apis", headers=applicant, json={**FORM, "responsible": "author@example.test"})
        .raise_for_status()
        .json()
    )
    assert row["responsible"] == subject
    url = "/api/apis/" + row["id"]
    submission = (
        portal.put(url + "/publication?published=true", headers=applicant).raise_for_status().json()
    )
    assert not submission["published"]
    assert portal.get(url, headers=lead).json()["publication_guidelines"] == rules["guidelines"]
    assert portal.get("/api/publication-requests", headers=lead).json()[0]["id"] == row["id"]
    users = {"admin": admin, "lead": lead, "applicant": applicant}
    for state in states[1:]:
        current = portal.get(url, headers=applicant).raise_for_status().json()
        result = portal.post(
            url + "/publication-decisions",
            headers=users[state["caller"]],
            json={"approved": True, "revision": current["revision"], "reason": "仕様を確認"},
        )
        assert result.status_code == state["response"], result.text
        assert bool(portal.get("/api/apis", headers=admin).json()) == state["listed"]


def test_publication_rejection_and_edits(portal):
    """公開申請の却下・修正・取り下げは以前の申請を終了し、古い判断では公開できない。"""
    owner, admin = headers(portal, "provider"), headers(portal, "admin")
    asset = portal.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()
    url = "/api/apis/" + asset["id"]
    publish = url + "/publication?published=true"
    pending = portal.put(publish, headers=owner).json()
    reason = {"approved": False, "reason": "責任者を確認", "revision": pending["revision"]}
    assert (
        portal.post("/api/apis/missing/publication-decisions", headers=admin, json=reason).status_code
        == 404
    )
    assert portal.put("/api/apis/missing/publication?published=true", headers=owner).status_code == 404
    result = (
        portal.post(url + "/publication-decisions", headers=admin, json=reason).raise_for_status().json()
    )
    assert not result["publication_stage"] and not result["published"]
    for cancel in ("edit", "withdraw"):
        pending = portal.put(publish, headers=owner).json()
        if cancel == "edit":
            portal.put(
                url, headers=owner, params={"revision": pending["revision"]}, json=FORM
            ).raise_for_status()
        else:
            portal.put(url + "/publication?published=false", headers=owner).raise_for_status()
        assert (
            portal.post(
                url + "/publication-decisions",
                headers=admin,
                json={**reason, "revision": pending["revision"]},
            ).status_code
            == 409
        )
    assert portal.get("/api/publication-requests", headers=admin).json() == []


def test_named_and_project_usage_approvals(portal):
    """指名された利用者と提供プロジェクトのリーダーが順番に承認した場合だけ利用権を発行する。"""
    owner, applicant, admin = (headers(portal, who) for who in ("provider", "consumer", "admin"))
    subject, lead = member(portal, admin, "leader")
    portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": subject, "unit_id": "supply", "leader": True},
    ).raise_for_status()
    form = {
        **FORM,
        "offers": {"sandbox": {"route": "custom", "steps": ["person/admin", "project_leader"]}},
    }
    row = portal.post("/api/apis", headers=owner, json=form).raise_for_status().json()
    assert row["responsible"] is None and row["owner"] == "supply"
    url = "/api/apis/" + row["id"]
    publish_asset(portal, url, owner).raise_for_status()
    grant = (
        portal.post(
            url + "/requests",
            headers=applicant,
            json={"project": "finance", "environment": "sandbox", "reason": "接続"},
        )
        .raise_for_status()
        .json()
    )
    for actor, status, next_stage in (
        (owner, 403, None),
        (admin, 200, "project_leader"),
        (lead, 200, None),
    ):
        response = portal.post(
            "/api/requests/" + grant["id"],
            headers=actor,
            json={"action": "approve", "reason": "用途確認", "revision": grant["revision"]},
        )
        assert response.status_code == status
        if status == 200:
            grant = response.json()
            assert grant["stage"] == next_stage
    assert grant["status"] == "approved"
