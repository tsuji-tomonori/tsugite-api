# 形式仕様に従い組織、問い合わせ、利用上限の各状態を実システムから読み戻す。
"""形式仕様に従い組織、問い合わせ、利用上限の各状態を実システムから読み戻す。"""

from uuid import UUID

import pytest
from app.apis.governance import alerts

from tests.support.catalog import approved, headers, invocation_headers
from tests.support.quint import histories


@pytest.mark.parametrize("states", histories("directory"))
def test_retirement_history(states, portal):
    """削除や無効な移管の後は子部署を保持し、有効な移管を再送しても所属先は一つになる。"""
    admin = headers(portal, "admin")
    base = "/api/workspace/units/"
    for key, kind, parent in (
        ("source", "department", ""),
        ("successor", "department", ""),
        ("child", "department", "source"),
        ("other", "project", ""),
    ):
        portal.put(
            base + key, headers=admin, json={"kind": kind, "name": key, "parent": parent}
        ).raise_for_status()
    targets = {"self": "source", "otherKind": "other", "transfer": "successor", "child": "child"}
    for step in states[1:]:
        op = step["operation"]
        if op == "delete":
            resp = portal.delete(base + "source", headers=admin)
        else:
            resp = portal.post(
                base + "source/transfer", headers=admin, json={"destination": targets[op]}
            )
        assert resp.status_code == step["response"], resp.text
        units = {u["id"]: u for u in portal.get("/api/workspace", headers=admin).json()["units"]}
        assert units["child"]["parent"] == step["parent"]
        assert ("source" in units) == (step["parent"] == "source")


@pytest.mark.parametrize("states", histories("inquiries"))
def test_private_inquiry_history(states, portal):
    """同じ受付番号で再送しても一件に保ち、他人の回答を拒み管理者の回答を本人に表示する。"""
    user, other, admin = (headers(portal, p) for p in ("consumer", "provider", "admin"))
    key = UUID(int=1)
    for step in states:
        op = step["operation"]
        if op == "submit":
            resp = portal.post(
                "/api/inquiries", headers=user, json={"inquiry_id": str(key), "question": "状態確認"}
            )
        elif op != "init":
            resp = portal.put(
                f"/api/inquiries/{key}/reply",
                headers=admin if op == "adminReply" else other,
                json={"answer": "確認しました"},
            )
        if op != "init":
            assert resp.status_code == step["response"]
        assert portal.get("/api/inquiries", headers=other).raise_for_status().json() == []
        rows = portal.get("/api/inquiries", headers=user).raise_for_status().json()
        assert len(rows) == int(step["submitted"])
        if rows:
            assert rows[0]["inquiry_id"] == key.hex
            assert bool(rows[0]["answer"]) == step["answered"]


@pytest.mark.parametrize("states", histories("quota"))
def test_threshold_history(states, portal, monkeypatch):
    """上限到達で一度通知し、次の呼び出しを拒否して新しい区間で再開する。"""
    owner, user = headers(portal, "provider"), headers(portal, "consumer")
    key, _, path = approved(portal, owner, user)
    token = invocation_headers(portal, user)
    now = 600
    monkeypatch.setattr(alerts, "time", lambda: now)
    portal.put(
        "/api/alerts",
        headers=owner,
        json={
            "asset_id": key,
            "project": "finance",
            "environment": "sandbox",
            "threshold": 2,
            "minutes": 1,
            "stop": True,
        },
    ).raise_for_status()
    for step in states:
        if step["operation"] == "invoke":
            assert portal.get(path, headers=token).status_code == step["response"]
        elif step["operation"] == "nextWindow":
            now += 60
        unread = portal.get("/api/notifications/count", headers=user).raise_for_status().json()["unread"]
        assert unread == step["notified"]


@pytest.mark.parametrize("states", histories("audit"))
def test_log_history(states, portal, monkeypatch):
    """監査の役割と呼出時の帰属に従い、本人画面と監査画面の詳細を照合する。"""
    from sqlalchemy.orm import Session
    from tsugite_db.models import AccessLog, LogUnit
    from tsugite_db.session import engine

    from packages.backend.tests.test_org_access import setup_people

    admin, people = setup_people(portal, monkeypatch)
    roles = {
        "member": people["applicant"],
        "lead": people["approver"],
        "admin": admin,
        "auditor": headers(portal, "auditor"),
    }
    with Session(engine()) as db:
        for trace, subject, project, unit in (
            ("mine", "applicant", "finance", "west"),
            ("peer", "another", "field", "east"),
            ("outside", "another", "finance", "west"),
        ):
            db.add(
                AccessLog(
                    request_id=trace,
                    actor=subject,
                    project=project,
                    owner="supply",
                    asset_id="stock",
                    environment="sandbox",
                    method="GET",
                    operation="/items",
                    status=200,
                    duration_ms=1,
                )
            )
            db.add(LogUnit(request_id=trace, unit_id=unit))
        db.commit()
    for step in states:
        trace = "mine" if step["own"] else "peer" if step["within"] else "outside"
        resp = portal.get(
            "/api/access-logs/detail",
            headers=roles[step["role"]],
            params={"request_id": trace, "scope": step["view"]},
        )
        assert resp.status_code == step["response"], step
        if resp.is_success:
            assert resp.json()["request_id"] == trace


@pytest.mark.parametrize("states", histories("notifications"))
def test_read_history(states, portal):
    """受信者ごとの未読数と、同じ通知を再度開いたときの件数を照合する。"""
    admin = headers(portal, "admin")
    users = {role: headers(portal, role) for role in ("consumer", "provider")}
    for step in states:
        op = step["operation"]
        if op == "send":
            notice = (
                portal.post(
                    "/api/notifications",
                    headers=admin,
                    json={"project": "*", "title": "全体周知", "body": "内容を確認してください"},
                )
                .raise_for_status()
                .json()["id"]
            )
        elif op in users:
            portal.put(f"/api/notifications/{notice}/read", headers=users[op]).raise_for_status()
        for who, identity in users.items():
            unread = (
                portal.get("/api/notifications/count", headers=identity)
                .raise_for_status()
                .json()["unread"]
            )
            assert unread == int(step["sent"] and who not in step["seen"]["#set"])


@pytest.mark.parametrize("states", histories("membership"))
def test_membership_history(states, portal):
    """一般利用者の所属付与、管理権限の変更、解除を本人の一覧から照合する。"""
    user, admin = headers(portal, "consumer"), headers(portal, "admin")
    unit = "quint-project"
    portal.put(
        "/api/workspace/units/" + unit, headers=admin, json={"kind": "project", "name": "検証"}
    ).raise_for_status()
    data = {"subject": "consumer", "unit_id": unit}
    for step in states:
        op = step["operation"]
        if op == "leave":
            portal.delete("/api/workspace/memberships", headers=admin, params=data).raise_for_status()
        elif op != "init":
            portal.put(
                "/api/workspace/memberships", headers=admin, json={**data, "leader": op == "lead"}
            ).raise_for_status()
        current = portal.get("/api/workspace", headers=user).raise_for_status().json()
        assert (unit in current["my_units"]) == step["member"]
        assert (unit in current["leads"]) == step["leader"]


@pytest.mark.parametrize("states", histories("profiles"))
def test_profile_history(states, portal):
    """本人と管理者が名前を更新し、第三者と旧版の書き込みが既存の値を変えない。"""
    people = {role: headers(portal, role) for role in ("consumer", "provider", "admin")}
    revision = 0
    for step in states:
        op = step["operation"]
        if op != "init":
            managed = op in ("other", "adminClear")
            identity = (
                people["provider"]
                if op == "other"
                else people["admin"]
                if managed
                else people["consumer"]
            )
            path = "/api/members/consumer/profile" if managed else "/api/me/profile"
            result = portal.patch(
                path,
                headers=identity,
                json={
                    "revision": 0 if op == "stale" else revision,
                    "display_name": "表示名" if op == "selfSet" else None,
                    **({"full_name": "利用 太郎"} if op == "selfSet" else {}),
                    **({"full_name": "　"} if op == "clearFull" else {}),
                },
            )
            assert result.status_code == step["response"], result.text
        current = portal.get("/api/me/profile", headers=people["consumer"]).raise_for_status().json()
        assert current["full_name"] == ("利用 太郎" if step["hasFullName"] else None)
        assert current["display_name"] == ("表示名" if step["named"] else None)
        revision = current["revision"]


@pytest.mark.parametrize("states", histories("slug"))
def test_reserved_name_history(states, portal):
    """重複・改名の拒否と、削除後も元の識別名が予約されていることを確かめる。"""
    from tests.support.catalog import FORM

    owner = headers(portal, "provider")
    asset = None
    for step in states[1:]:
        op = step["operation"]
        if op in {"invalid", "create"}:
            form = {**FORM, "slug": "invalid/name"} if op == "invalid" else FORM
            response = portal.post("/api/apis", headers=owner, json=form)
            if response.status_code == 201:
                asset = response.json()
        else:
            assert asset is not None
            url = "/api/apis/" + asset["id"]
            params = {"revision": asset["revision"]}
            if op == "rename":
                response = portal.put(url, params=params, headers=owner, json={**FORM, "slug": "new"})
            else:
                assert op == "delete"
                response = portal.delete(url, params=params, headers=owner)
        assert response.status_code == step["response"], (op, response.text)
        items = portal.get("/api/apis?inventory=true", headers=owner).raise_for_status().json()
        assert any(item["slug"] == FORM["slug"] for item in items) == (step["lifecycle"] == "listed")


@pytest.mark.parametrize("states", histories("email"))
def test_directory_email_history(states):
    """同期候補と本人確認結果を変え、既存氏名と保存した連絡先を各段階で読む。"""
    from unittest.mock import Mock

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from tsugite_db.models import Base, Member, MemberProfile, now

    from packages.tools.operations.sync_member_emails import sync
    from packages.tools.tests.test_sync_member_emails import record

    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        with Session(connection) as db:
            db.add(Member(subject="user", username="user", project="", role="consumer", deleted=False))
            db.add(
                MemberProfile(
                    subject="user",
                    full_name="利用 太郎",
                    email="old@example.test",
                    email_synced_at=now(),
                )
            )
            db.commit()
        for step in states[1:]:
            op = step["operation"]
            idp = Mock()
            contact = "new@example.test"
            idp.get_paginator.return_value.paginate.return_value = [{"Users": [record("user", contact)]}]
            confirmed = record("other" if op == "mismatch" else "user", contact, listed=False)
            idp.admin_get_user.return_value = {**confirmed, "Enabled": op != "disabled"}
            with Session(connection) as db:
                db.get_one(Member, "user").deleted = op == "retired"
                db.commit()
            sync(idp, connection, "pool", apply=op != "preview")
            assert bool(idp.admin_get_user.call_count) == step["verified"]
            with Session(connection) as db:
                profile = db.get_one(MemberProfile, "user")
                assert profile.full_name == "利用 太郎"
                assert profile.email == (contact if step["updated"] else "old@example.test")
