"""入退社とプロフィールの要件を、会員一覧・所属一覧・監査から照合する。"""

import pytest

from tests.support.catalog import headers


@pytest.mark.parametrize(
    "role",
    [
        pytest.param(
            "consumer",
            id="consumer",
            marks=pytest.mark.case_detail("利用者として招待して会員一覧に反映する"),
        ),
        pytest.param(
            "provider",
            id="provider",
            marks=pytest.mark.case_detail("提供者として招待して会員一覧に反映する"),
        ),
    ],
)
def test_invitation_profile_and_retirement(portal, role):
    """招待時の氏名・表示名は所属一覧に載り、管理者による変更と退会は対象者に反映される。"""
    admin = headers(portal, "admin")
    project = portal.get("/api/members", headers=admin).json()["projects"][0]
    invitation = {
        "email": f"new-{role}@example.com",
        "project": project,
        "role": role,
        "full_name": "企画 太郎",
        "display_name": "たろう",
    }
    response = portal.post("/api/members", headers=admin, json=invitation)
    assert response.status_code == 201
    person = response.json()
    subject = person["subject"]
    assert subject and person["username"]
    for field in ("full_name", "display_name", "email"):
        assert person[field] == invitation[field]

    url = f"/api/members/{subject}/profile"
    profile = portal.get(url, headers=admin).json()
    changed = portal.patch(
        url, headers=admin, json={"revision": profile["revision"], "display_name": "企画担当"}
    )
    assert changed.status_code == 200
    assert changed.json()["full_name"] == invitation["full_name"]
    assert changed.json()["display_name"] == "企画担当"

    listing = portal.get("/api/members", headers=admin, params={"limit": 1}).json()
    members = listing["items"].copy()
    cursors = set()
    while listing["next"]:
        cursor = listing["next"]
        assert cursor not in cursors
        cursors.add(cursor)
        listing = portal.get("/api/members", headers=admin, params={"limit": 1, "cursor": cursor}).json()
        assert len(listing["items"]) <= 1
        members.extend(listing["items"])
    listed = [m for m in members if m["subject"] == subject]
    assert len(listed) == 1 and "role" not in listed[0]
    workspace = portal.get("/api/workspace", headers=admin).json()
    assert any(
        m["subject"] == subject
        and m["unit_id"] == project
        and m["display_name"] == "企画担当"
        and m["full_name"] == invitation["full_name"]
        and m["email"] == invitation["email"]
        for m in workspace["memberships"]
    )
    removed = portal.delete(
        f"/api/members/{subject}",
        params={"username": person["username"]},
        headers=admin,
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"]
    page = portal.get("/api/members", params={"limit": 60}, headers=admin).json()
    assert not any(m["subject"] == subject and not m.get("deleted") for m in page["items"])


def test_self_edit_conflict_and_clear(portal):
    """本人のプロフィール変更が古い編集画面から失われず、氏名の削除を拒否し、表示名だけをクリアできる。"""
    user = headers(portal, "consumer")
    auditor = headers(portal, "auditor")
    url = "/api/me/profile"
    original = portal.get(url, headers=user).json()
    names = {"full_name": "氏" * 120, "display_name": "名" * 80}
    changed = portal.patch(url, headers=user, json={**names, "revision": original["revision"]})
    assert changed.status_code == 200
    profile = changed.json()
    assert profile["revision"] > original["revision"]
    assert all(profile[key] == value for key, value in names.items())
    audit = portal.get(
        "/api/audit", headers=auditor, params={"request_id": changed.headers["x-request-id"]}
    )
    assert audit.status_code == 200
    assert any(row["actor"] == row["target_subject"] == original["subject"] for row in audit.json())
    conflict = portal.patch(
        url, headers=user, json={"full_name": "別の氏名", "revision": original["revision"]}
    )
    assert conflict.status_code == 409
    assert portal.get(url, headers=user).json() == profile
    cleared = portal.patch(
        url,
        headers=user,
        json={"full_name": None, "display_name": None, "revision": profile["revision"]},
    )
    assert cleared.status_code == 422
    assert portal.get(url, headers=user).json() == profile
    cleared = portal.patch(
        url, headers=user, json={"display_name": None, "revision": profile["revision"]}
    )
    assert cleared.raise_for_status().json()["full_name"] == names["full_name"]
    assert cleared.json()["display_name"] is None
    assert portal.get("/api/me", headers=user).json()["subject"] == original["subject"]
