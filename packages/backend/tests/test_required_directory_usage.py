# 管轄部署の利用状況に表示する所属者を、外部名簿のページ境界と所属履歴を含めて検証する。
import boto3
from app.apis.governance import directory
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
