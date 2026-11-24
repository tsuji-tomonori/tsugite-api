# Cognitoを利用する会員名簿で、招待・閲覧・退会と外部サービスの応答を検証する。

from unittest.mock import Mock

import boto3
import pytest

from tests.support.catalog import headers


def _directory(monkeypatch):
    for module in ("members", "directory", "profiles"):
        root = f"app.apis.governance.{module}"
        monkeypatch.setattr(f"{root}.local_demo", lambda: False, raising=False)
        monkeypatch.setattr(f"{root}.settings", lambda: {"pool_id": "test-pool"}, raising=False)
    cognito = boto3.client(
        "cognito-idp", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing",
    )
    directory = Mock()
    directory.exceptions = cognito.exceptions
    directory.list_users_in_group.return_value = {"Users": []}
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: directory)
    return directory


def _external_member(email, subject):
    return {
        "Username": email, "Enabled": True, "UserStatus": "CONFIRMED",
        "Attributes": [{"Name": "sub", "Value": subject}, {"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}],
    }


def test_external_directory_pagination(portal, monkeypatch):
    """外部名簿の続きがあるとき、公開カーソルで次ページに進み、各人のメールと識別子を保持する。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    first = _external_member("new@example.com", "staff-001")
    second = _external_member("another@example.com", "staff-002")
    client.admin_create_user.return_value = {"User": first}
    invitation = {"email": "new@example.com", "role": "consumer", "project": "finance", "display_name": "新人"}
    assert portal.post("/api/members", headers=admin, json=invitation).status_code == 201
    client.list_users.side_effect = [
        {"Users": [first], "PaginationToken": "page-two"}, {"Users": [second]},
    ]
    page = portal.get("/api/members", headers=admin, params={"limit": 1})
    assert page.status_code == 200
    assert [(m["subject"], m["email"]) for m in page.json()["items"]] == [("staff-001", "new@example.com")]
    assert page.json()["next"]
    following = portal.get("/api/members", headers=admin, params={"limit": 1, "cursor": page.json()["next"]})
    assert following.status_code == 200
    assert [(m["subject"], m["username"]) for m in following.json()["items"]] == [("staff-002", "another@example.com")]
    assert not following.json()["next"]


@pytest.mark.parametrize(
    "role",
    [
        pytest.param("consumer", id="consumer", marks=pytest.mark.case_detail("招待した利用者の氏名とメールアドレスを取得できる")),
        pytest.param("provider", id="provider", marks=pytest.mark.case_detail("提供者として招待した人も同じ名簿で退会できる")),
    ],
)
def test_external_invitation_and_retirement(portal, monkeypatch, role):
    """Cognitoで招待を受け付けた対象者のプロフィールを保存し、退会時も同じアカウントを操作する。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "new-hire@example.com"
    subject = "invited-001"
    account = _external_member(email, subject)
    client.list_users.return_value = {"Users": [account]}
    client.admin_create_user.return_value = {"User": account}
    client.admin_get_user.return_value = {"Username": email, "Enabled": True, "UserStatus": "CONFIRMED", "UserAttributes": account["Attributes"]}
    payload = {"role": role, "project": "finance", "email": email, "full_name": "入社 花子", "display_name": "花子"}
    invited = portal.post("/api/members", headers=admin, json=payload)
    assert invited.status_code == 201, invited.json()
    person = invited.json()
    assert (person["subject"], person["username"], person["email"]) == (subject, email, email)
    profile = portal.get(f"/api/members/{subject}/profile", headers=admin)
    assert profile.status_code == 200, profile.json()
    assert profile.json()["full_name"] == "入社 花子" and profile.json()["display_name"] == "花子"
    retired = portal.delete(f"/api/members/{subject}", headers=admin, params={"username": person["username"]})
    assert retired.status_code == 200, retired.json()
    assert retired.json()["deleted"]
    assert client.admin_delete_user.call_args.kwargs["Username"] == email


def test_duplicate_external_invitation_preserves_original_member(portal, monkeypatch):
    """Cognitoで既存のメールアドレスを再招待すると競合を通知し、既存アカウントを削除しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.admin_create_user.side_effect = client.exceptions.UsernameExistsException(
        {"Error": {"Code": "UsernameExistsException", "Message": "User already exists"}}, "AdminCreateUser",
    )
    invitation = {"email": "member@example.com", "role": "consumer", "project": "finance"}
    response = portal.post("/api/members", headers=admin, json=invitation)
    assert response.status_code == 409, response.json()
    assert response.json()["detail"]
    client.admin_delete_user.assert_not_called()


def test_directory_temporarily_unavailable(portal, monkeypatch):
    """外部名簿が一時的に利用できなければ一覧APIはサービス障害を返し、復旧後に同じページを読める。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.list_users.side_effect = [
        client.exceptions.InternalErrorException({"Error": {"Code": "InternalErrorException", "Message": "Temporary failure"}}, "ListUsers"),
        {"Users": []},
    ]
    failed = portal.get("/api/members", headers=admin)
    assert failed.status_code == 503 and failed.json()["detail"]
    recovered = portal.get("/api/members", headers=admin)
    assert recovered.status_code == 200 and recovered.json()["items"] == []


def test_failed_group_assignment_cleans_up_new_invitation(portal, monkeypatch):
    """招待先の役割を付与できなければ作成途中のアカウントを取り消し、同じ人を改めて招待できる。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "retry@example.com"
    account = _external_member(email, "retry-person")
    client.admin_create_user.return_value = {"User": account}
    client.admin_add_user_to_group.side_effect = [
        client.exceptions.ResourceNotFoundException(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Group unavailable"}}, "AdminAddUserToGroup",
        ),
        {},
    ]
    invitation = {"email": email, "project": "finance", "role": "consumer"}
    failed = portal.post("/api/members", headers=admin, json=invitation)
    assert 400 <= failed.status_code < 600 and failed.json()["detail"]
    client.admin_delete_user.assert_called_once_with(UserPoolId="test-pool", Username=email)
    retried = portal.post("/api/members", headers=admin, json=invitation)
    assert retried.status_code == 201
    assert retried.json()["subject"] == "retry-person"


def test_external_directory_source_for_membership(portal, monkeypatch):
    """Cognitoで登録した人を部署に所属させると、その識別子・ログイン名・役職で名簿を更新できる。"""
    admin = headers(portal, "admin")
    unit = portal.put("/api/workspace/units/field", headers=admin, json={"name": "現場", "kind": "department"})
    assert unit.status_code == 200
    client = _directory(monkeypatch)
    person = _external_member("field@example.com", "field-staff")
    client.list_users.return_value = {"Users": [person]}
    client.admin_get_user.return_value = {
        "Username": person["Username"], "UserAttributes": person["Attributes"], "Enabled": True,
    }
    listing = portal.get("/api/members", headers=admin)
    assert listing.status_code == 200
    assert any(row["subject"] == "field-staff" and row["username"] == person["Username"] for row in listing.json()["items"])
    added = portal.put(
        "/api/workspace/memberships", headers=admin,
        json={"subject": "field-staff", "unit_id": "field", "leader": True, "title": "現場監督"},
    )
    assert added.status_code == 200, added.json()
    usage = portal.get("/api/workspace/units/field/usage", headers=admin)
    assert usage.status_code == 200
    members = usage.json()["members"]
    assert any(row["subject"] == "field-staff" and row["title"] == "現場監督" and row["leader"] for row in members)
    removed = portal.delete(
        "/api/workspace/memberships", headers=admin, params={"subject": "field-staff", "unit_id": "field"},
    )
    assert removed.status_code == 200 and removed.json()["removed"]


def test_unknown_cognito_member_cannot_be_assigned(portal, monkeypatch):
    """名簿に該当する利用者がいない場合は、組織への所属を作成しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.list_users.return_value = {"Users": []}
    client.admin_get_user.side_effect = client.exceptions.UserNotFoundException(
        {"Error": {"Code": "UserNotFoundException", "Message": "No such user"}}, "AdminGetUser",
    )
    failed = portal.put(
        "/api/workspace/memberships", headers=admin, json={"subject": "former-staff", "unit_id": "finance"},
    )
    assert failed.status_code == 404 and failed.json()["detail"]
    current = portal.get("/api/workspace/units/finance/usage", headers=admin).json()
    assert not any(row["subject"] == "former-staff" for row in current["members"])


def test_external_member_disappears_before_profile_edit(portal, monkeypatch):
    """外部名簿から退会済みの利用者を再編集したとき、対象者が見つからないことを管理者へ返す。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    member = _external_member("retired@example.com", "retired-subject")
    client.admin_create_user.return_value = {"User": member}
    invited = portal.post(
        "/api/members", headers=admin, json={"email": member["Username"], "role": "provider", "project": "supply"},
    )
    assert invited.status_code == 201
    client.admin_get_user.side_effect = client.exceptions.UserNotFoundException(
        {"Error": {"Code": "UserNotFoundException", "Message": "Retired"}}, "AdminGetUser",
    )
    url = f"/api/members/{invited.json()['subject']}/profile"
    missing = portal.patch(url, headers=admin, json={"revision": 0, "display_name": "新名称"})
    assert missing.status_code == 404 and missing.json()["detail"]
