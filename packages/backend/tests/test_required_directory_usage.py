# 管轄部署の利用状況に表示する所属者を、外部名簿のページ境界と所属履歴を含めて検証する。
from types import SimpleNamespace

import boto3
from app.apis.governance import directory
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from tsugite_db.models import Affiliation, Member
from tsugite_db.session import engine

from tests.support.catalog import headers


def test_usage_combines_cognito_pages_without_reviving_removed_members(portal, monkeypatch):
    """部署と管轄プロジェクトの利用状況に外部名簿の全ページを反映し、退会者と所属解除者を除く。"""
    admin = headers(portal, "admin")
    for key, data in (
        ("audit-office", {"kind": "department", "name": "監査室"}),
        ("finance", {"kind": "project", "name": "経理", "parent": "audit-office"}),
    ):
        response = portal.put(f"/api/workspace/units/{key}", headers=admin, json=data)
        assert response.status_code == 200, response.text
    with Session(engine()) as db:
        db.add(
            Member(subject="resigned", username="former", project="finance", role="use", deleted=True)
        )
        db.add(Affiliation(subject="released", unit_id="finance", title="", leader=False, active=False))
        db.commit()

    def record(subject):
        return {
            "Username": "login-" + subject,
            "Enabled": True,
            "Attributes": [{"Name": "sub", "Value": subject}],
        }

    class GroupDirectory:
        def __init__(self):
            self.pages = []

        def list_users_in_group(self, *, UserPoolId, GroupName, NextToken=None):
            assert UserPoolId == "pool-usage"
            self.pages.append((GroupName, NextToken))
            if GroupName == "use-finance" and NextToken is None:
                return {"Users": [record("first"), record("released")], "NextToken": "remaining"}
            if GroupName == "use-finance" and NextToken == "remaining":
                return {"Users": [record("second"), record("resigned")]}
            if GroupName == "own-finance":
                return {"Users": [record("first"), record("owner")]}
            raise AssertionError(f"管轄外のグループを照会しました {GroupName}")

    groups = GroupDirectory()
    monkeypatch.setattr(directory, "local_demo", lambda: False)
    monkeypatch.setattr(
        directory, "settings", lambda: {"pool_id": "pool-usage", "projects": ["finance"]}
    )
    monkeypatch.setattr(boto3, "client", lambda name: groups)
    for key in ("audit-office", "finance"):
        groups.pages.clear()
        response = portal.get(f"/api/workspace/units/{key}/usage", headers=admin)
        assert response.status_code == 200, response.text
        members = response.json()["members"]
        subjects = [entry["subject"] for entry in members]
        assert {"first", "second", "owner"} <= set(subjects)
        assert not {"resigned", "released"}.intersection(subjects)
        assert subjects.count("first") == 1
        for entry in members:
            if entry["subject"] in {"first", "second", "owner"}:
                assert entry["unit_id"] == "finance"
                assert entry["username"] == "login-" + entry["subject"]
        assert set(groups.pages) == {
            ("use-finance", None),
            ("use-finance", "remaining"),
            ("own-finance", None),
        }


def test_department_usage_preserves_assigned_roles_and_excludes_other_projects(portal, monkeypatch):
    """部署の実績では直接付与した役職を保持し、他部署の利用者や存在しないグループを含めない。"""
    admin = headers(portal, "admin")
    for key, kind, parent in (
        ("service", "department", ""),
        ("research", "department", ""),
        ("finance", "project", "service"),
        ("supply", "project", "research"),
    ):
        saved = portal.put(
            f"/api/workspace/units/{key}",
            headers=admin,
            json={"kind": kind, "name": key, "parent": parent},
        )
        assert saved.status_code == 200, saved.text
    with Session(engine()) as db:
        for subject, team, title in (
            ("supervisor", "finance", "会計主管"),
            ("outside", "supply", "研究主任"),
        ):
            db.add(Member(subject=subject, username=subject, project=team, role="use", deleted=False))
            db.add(Affiliation(subject=subject, unit_id=team, title=title, leader=True, active=True))
        db.commit()

    class MissingGroup(ClientError):
        pass

    class Directory:
        exceptions = SimpleNamespace(ResourceNotFoundException=MissingGroup)

        def list_users_in_group(self, *, UserPoolId, GroupName):
            assert UserPoolId == "pool-roles"
            if GroupName == "own-finance":
                raise MissingGroup({"Error": {"Code": "ResourceNotFoundException"}}, "ListUsersInGroup")
            assert GroupName == "use-finance"
            return {
                "Users": [
                    {"Username": "login", "Attributes": [{"Name": "sub", "Value": "supervisor"}]},
                    {"Username": "unidentified", "Attributes": []},
                ]
            }

    monkeypatch.setattr(directory, "local_demo", lambda: False)
    monkeypatch.setattr(
        directory, "settings", lambda: {"pool_id": "pool-roles", "projects": ["finance", "supply"]}
    )
    monkeypatch.setattr(boto3, "client", lambda name: Directory())
    result = portal.get("/api/workspace/units/service/usage", headers=admin)
    assert result.status_code == 200, result.text
    members = result.json()["members"]
    assert all(row["subject"] != "outside" for row in members)
    direct = [row for row in members if row["subject"] == "supervisor"]
    assert len(direct) == 1
    assert direct[0]["title"] == "会計主管" and direct[0]["leader"]


def test_transferred_project_reports_only_its_current_membership(portal):
    """プロジェクトを移管すると移管先の実績に所属と役職を引き継ぎ、廃止した元の実績は開けない。"""
    admin = headers(portal, "admin")
    for key in ("former-reporting", "current-reporting"):
        created = portal.put(
            f"/api/workspace/units/{key}",
            headers=admin,
            json={"kind": "project", "name": key},
        )
        assert created.status_code == 200
    with Session(engine()) as db:
        db.add(
            Member(subject="supervisor", username="controller", project="former-reporting", role="use")
        )
        db.add(
            Affiliation(
                subject="supervisor",
                unit_id="former-reporting",
                title="経理主任",
                leader=True,
                active=True,
            )
        )
        db.commit()
    moved = portal.post(
        "/api/workspace/units/former-reporting/transfer",
        headers=admin,
        json={"destination": "current-reporting"},
    )
    assert moved.status_code == 200, moved.text
    result = portal.get("/api/workspace/units/current-reporting/usage", headers=admin)
    assert result.status_code == 200
    person = next(p for p in result.json()["members"] if p["subject"] == "supervisor")
    assert (
        person["unit_id"] == "current-reporting" and person["title"] == "経理主任" and person["leader"]
    )
    workspace = portal.get("/api/workspace", headers=admin).json()
    assert "former-reporting" not in {unit["id"] for unit in workspace["units"]}
    retired = portal.get("/api/workspace/units/former-reporting/usage", headers=admin)
    assert retired.status_code in {403, 404} and "members" not in retired.json()


def test_local_directory_keeps_legacy_members_but_excludes_deleted_demo_accounts(portal):
    """従来のプロジェクト所属を実績画面に表示し、退会済みデモ利用者を標準の所属から復活させない。"""
    admin = headers(portal, "admin")
    with Session(engine()) as db:
        db.merge(
            Member(subject="consumer", username="consumer", project="finance", role="use", deleted=True)
        )
        db.add(Member(subject="legacy", username="legacy-account", project="finance", role="use"))
        db.add(Member(subject="independent", username="individual", project="", role="use"))
        db.commit()
    result = portal.get("/api/workspace/units/finance/usage", headers=admin)
    assert result.status_code == 200
    members = result.json()["members"]
    legacy = [member for member in members if member["subject"] == "legacy"]
    assert len(legacy) == 1
    assert legacy[0]["username"] == "legacy-account" and legacy[0]["unit_id"] == "finance"
    assert not {member["subject"] for member in members}.intersection({"consumer", "independent"})


def test_retired_configured_project_stays_hidden_with_stale_local_memberships(portal):
    """既定プロジェクトの移管後も旧グループや旧形式の所属から廃止したプロジェクトを再表示しない。"""
    admin = headers(portal, "admin")
    destination = "budgeting"
    created = portal.put(
        "/api/workspace/units/" + destination,
        headers=admin,
        json={"kind": "project", "name": "予算管理"},
    )
    assert created.status_code == 200
    moved = portal.post(
        "/api/workspace/units/finance/transfer", headers=admin, json={"destination": destination}
    )
    assert moved.status_code == 200, moved.text
    with Session(engine()) as db:
        db.add(
            Member(subject="stale-account", username="former-affiliation", project="finance", role="use")
        )
        db.commit()
    workspace = portal.get("/api/workspace", headers=admin).json()
    assert "finance" not in {item["id"] for item in workspace["units"]}
    assert not any(item["unit_id"] == "finance" for item in workspace["memberships"])
    assert portal.get("/api/workspace/units/finance/usage", headers=admin).status_code in {403, 404}
