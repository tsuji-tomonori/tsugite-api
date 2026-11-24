from unittest.mock import Mock

from app.apis.governance import profiles
from sqlalchemy.orm import Session
from tsugite_db.models import Member, MemberProfile, now
from tsugite_db.session import engine

from tests.support.catalog import headers


def test_profile_edits_filter_directory_and_audit(portal):
    """本人と全体管理者の変更を兼務先に反映し、IDと監査の閲覧範囲を保持する。"""
    admin = headers(portal, "admin")
    auditor = headers(portal, "auditor")
    leader = headers(portal, "consumer")
    email = "invite-profile@example.test"
    project = "finance"
    department = "accounts-team"
    created = portal.post(
        "/api/members",
        headers=admin,
        json={"email": email, "project": project, "role": "consumer", "full_name": " 高橋 美咲 "},
    )
    assert created.status_code == 201
    item = created.json()
    subject = item["subject"]
    assert item == dict(
        subject=subject, username=email, email=email, full_name="高橋 美咲", display_name=None
    )
    check = headers(portal, email)
    my_profile = "/api/me/profile"
    managed_profile = f"/api/members/{subject}/profile"
    portal.put(
        f"/api/workspace/units/{department}",
        json={"kind": "department", "name": "経理部"},
        headers=admin,
    ).raise_for_status()
    for identity, unit, manages in (
        (subject, department, False),
        ("consumer", department, True),
        ("consumer", project, True),
    ):
        portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": identity, "unit_id": unit, "leader": manages},
        ).raise_for_status()
    before = portal.get("/api/me", headers=check).raise_for_status().json()
    profile = portal.get(my_profile, headers=check).raise_for_status().json()
    assert profile == dict(
        subject=subject, email=email, full_name="高橋 美咲", display_name=None, revision=1
    )
    assert portal.get(my_profile).status_code == 401
    assert portal.get(managed_profile, headers=leader).status_code == 403
    assert portal.get("/api/members/unknown/profile", headers=admin).status_code == 404
    assert (
        portal.patch(
            managed_profile, headers=leader, json={"revision": 1, "full_name": "改名"}
        ).status_code
        == 403
    )
    for invalid in (
        {"email": "changed@example.test"},
        {"full_name": "\n氏名"},
        {"display_name": "続" * 81},
    ):
        assert (
            portal.patch(my_profile, headers=check, json={"revision": 1, **invalid}).status_code == 422
        )
    response = portal.patch(my_profile, headers=check, json={"revision": 1, "display_name": "みさき"})
    response.raise_for_status()
    assert response.json()["full_name"] == "高橋 美咲"
    assert response.json()["revision"] == 2
    assert portal.get("/api/me", headers=check).raise_for_status().json() == before
    for identity, unit_ids in ((admin, {project, department}), (leader, {project, department})):
        data = portal.get("/api/workspace", headers=identity).raise_for_status().json()
        shown = [row for row in data["memberships"] if row["subject"] == subject]
        assert {row["unit_id"] for row in shown} == unit_ids
        assert all(row["email"] == email and row["display_name"] == "みさき" for row in shown)

    outside = portal.get("/api/workspace", headers=headers(portal, "provider")).raise_for_status().json()
    assert all(
        row["subject"] != subject for section in ("users", "memberships") for row in outside[section]
    )
    assert (
        portal.patch(my_profile, headers=check, json={"revision": 1, "display_name": None}).status_code
        == 409
    )
    updated = portal.patch(managed_profile, headers=admin, json={"revision": 2, "display_name": " "})
    assert updated.raise_for_status().json()["display_name"] is None
    assert updated.json()["full_name"] == "高橋 美咲"
    unchanged = portal.patch(managed_profile, headers=admin, json={"revision": 3, "display_name": None})
    assert unchanged.raise_for_status().json()["revision"] == 3

    params = {"request_id": updated.headers["x-request-id"], "action": "profile.admin_update"}
    events = portal.get("/api/audit", headers=auditor, params=params).raise_for_status().json()
    (event,) = events
    assert (event["actor"], event["target_subject"], event["detail"]) == (
        "admin",
        subject,
        "display_name",
    )
    assert email not in str(event) and "高橋" not in str(event)
    assert portal.get("/api/audit", headers=leader, params=params).json() == []
    self_event = (
        portal.get("/api/audit", headers=admin, params={"request_id": response.headers["x-request-id"]})
        .raise_for_status()
        .json()
    )
    assert self_event[0]["actor"] == self_event[0]["target_subject"] == subject
    all_admin_changes = (
        portal.get("/api/audit", headers=admin, params={"action": "profile.admin_update"})
        .raise_for_status()
        .json()
    )
    assert len(all_admin_changes) == 1
    portal.delete(
        f"/api/members/{subject}", headers=admin, params={"username": email}
    ).raise_for_status()
    assert portal.get(my_profile, headers=check).status_code == 403
    assert portal.get(managed_profile, headers=admin).status_code == 404
    with Session(engine()) as db:
        row = db.get(MemberProfile, subject)
        assert row is not None and (row.email, row.full_name, row.display_name) == (None, None, None)
    assert portal.get("/api/audit", headers=auditor, params=params).json() == events


def test_legacy_profile_first_edit(portal):
    """既存のメール招待・アカウント行のない利用者は、任意の氏名を初回保存できる。"""
    with Session(engine()) as db:
        db.add(
            Member(
                subject="legacy-id", username="legacy@example.test", role="consumer", project="finance"
            )
        )
        db.add(
            Member(subject="external-id", username="external@example.test", role="external", project="")
        )
        db.commit()
    path = "/api/me/profile"
    actor = headers(portal, "legacy@example.test")
    before = portal.get(path, headers=actor).raise_for_status().json()
    assert before == dict(
        subject="legacy-id", email="legacy@example.test", full_name=None, display_name=None, revision=0
    )
    own = headers(portal, "provider")
    version = portal.get(path, headers=own).raise_for_status().json()
    assert version["revision"] == 0 and version["email"] is None
    saved = portal.patch(path, headers=own, json={"revision": 0, "display_name": "表示だけ"})
    assert saved.raise_for_status().json()["revision"] == 1
    assert saved.json()["subject"] == "provider"
    with Session(engine()) as db:
        assert db.get(Member, "provider") is None
        legacy = db.get(Member, "legacy-id")
        assert legacy is not None
        legacy_profile = MemberProfile(subject="legacy-id", email_synced_at=now())
        db.add(legacy_profile)
        db.commit()
    assert portal.get(path, headers=actor).raise_for_status().json()["email"] is None


def test_managed_cognito_only_account_requires_matching_subject(portal, monkeypatch):
    """Cognitoだけにある利用者は確認時のsubが一致し、かつ有効なときだけ管理者が編集できる。"""
    idp = Mock()
    idp.list_users.return_value = {"Users": [{"Username": "initial-admin"}]}
    idp.admin_get_user.return_value = {
        "Enabled": True,
        "UserAttributes": [{"Name": "sub", "Value": "known-sub"}],
    }
    monkeypatch.setattr(profiles, "local_demo", lambda: False)
    monkeypatch.setattr(profiles, "pool", lambda: "test-pool")
    monkeypatch.setattr(profiles.boto3, "client", lambda _: idp)
    path = "/api/members/known-sub/profile"
    admin = headers(portal, "admin")
    assert portal.get(path, headers=admin).raise_for_status().json()["revision"] == 0
    idp.list_users.assert_called_with(UserPoolId="test-pool", Filter='sub = "known-sub"')
    payload = {"revision": 0, "full_name": "初期 管理者"}
    assert (
        portal.patch(path, headers=admin, json=payload).raise_for_status().json()["full_name"]
        == "初期 管理者"
    )
    idp.admin_get_user.return_value["UserAttributes"][0]["Value"] = "another-sub"
    assert portal.get(path, headers=admin).status_code == 404
    with Session(engine()) as db:
        assert db.get(Member, "known-sub") is None
