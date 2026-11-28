# 個人アカウントへの管理者権限の引き継ぎを検証する。
import pytest

from tests.support.catalog import headers
from tests.support.quint import histories


@pytest.mark.parametrize("states", histories("administrators"))
def test_admin_role_handover(states, portal):
    """管理者が交代しても同じログインで権限が切り替わり、最後の一人は残る。"""
    first = headers(portal, "admin")
    email = "operator@example.test"
    person = (
        portal.post(
            "/api/members",
            headers=first,
            json={"email": email, "full_name": "管理 花子", "project": "supply"},
        )
        .raise_for_status()
        .json()
    )
    sessions = {"first": first, "second": headers(portal, email)}
    subjects = {"first": "admin", "second": person["subject"]}
    for state in states[1:]:
        target = subjects[state["target"]]
        result = portal.put(
            f"/api/members/{target}/admin-role",
            headers=sessions[state["caller"]],
            json={"admin": state["grant"]},
        )
        assert result.status_code == state["response"], result.text
        for who, token in sessions.items():
            me = portal.get("/api/me", headers=token).raise_for_status().json()
            assert me["admin"] == state[who]
            if who == "second":
                assert me["owners"] == me["projects"] == [state["project"]]
            listing = portal.get("/api/members", headers=token)
            if state[who]:
                assert {r["subject"] for r in listing.json()["items"] if r["admin"]} == {
                    subjects[name] for name in sessions if state[name]
                }
            else:
                assert listing.status_code == 403
