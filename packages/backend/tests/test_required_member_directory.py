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
        "cognito-idp",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    directory = Mock()
    directory.exceptions = cognito.exceptions
    directory.list_users_in_group.return_value = {"Users": []}
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: directory)
    return directory


def _external_member(email, subject):
    return {
        "Username": email,
        "Enabled": True,
        "UserStatus": "CONFIRMED",
        "Attributes": [
            {"Name": "sub", "Value": subject},
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
    }


def test_external_directory_pagination(portal, monkeypatch):
    """外部名簿の続きがあるとき、公開カーソルで次ページに進み、各人のメールと識別子を保持する。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    first = _external_member("new@example.com", "staff-001")
    second = _external_member("another@example.com", "staff-002")
    client.admin_create_user.return_value = {"User": first}
    invitation = {
        "full_name": "試験 花子",
        "email": "new@example.com",
        "role": "consumer",
        "project": "finance",
        "display_name": "新人",
    }
    assert portal.post("/api/members", headers=admin, json=invitation).status_code == 201
    client.list_users.side_effect = [
        {"Users": [first], "PaginationToken": "page-two"},
        {"Users": [second]},
    ]
    page = portal.get("/api/members", headers=admin, params={"limit": 1})
    assert page.status_code == 200
    assert [(m["subject"], m["email"]) for m in page.json()["items"]] == [
        ("staff-001", "new@example.com")
    ]
    assert page.json()["next"]
    following = portal.get(
        "/api/members", headers=admin, params={"limit": 1, "cursor": page.json()["next"]}
    )
    assert following.status_code == 200
    assert [(m["subject"], m["username"]) for m in following.json()["items"]] == [
        ("staff-002", "another@example.com")
    ]
    assert not following.json()["next"]


@pytest.mark.parametrize(
    "role",
    [
        pytest.param(
            "consumer",
            id="consumer",
            marks=pytest.mark.case_detail("招待した利用者の氏名とメールアドレスを取得できる"),
        ),
        pytest.param(
            "provider",
            id="provider",
            marks=pytest.mark.case_detail("提供者として招待した人も同じ名簿で退会できる"),
        ),
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
    client.admin_get_user.return_value = {
        "Username": email,
        "Enabled": True,
        "UserStatus": "CONFIRMED",
        "UserAttributes": account["Attributes"],
    }
    payload = {
        "role": role,
        "project": "finance",
        "email": email,
        "full_name": "入社 花子",
        "display_name": "花子",
    }
    invited = portal.post("/api/members", headers=admin, json=payload)
    assert invited.status_code == 201, invited.json()
    person = invited.json()
    assert (person["subject"], person["username"], person["email"]) == (subject, email, email)
    profile = portal.get(f"/api/members/{subject}/profile", headers=admin)
    assert profile.status_code == 200, profile.json()
    assert profile.json()["full_name"] == "入社 花子" and profile.json()["display_name"] == "花子"
    retired = portal.delete(
        f"/api/members/{subject}", headers=admin, params={"username": person["username"]}
    )
    assert retired.status_code == 200, retired.json()
    assert retired.json()["deleted"]
    assert client.admin_delete_user.call_args.kwargs["Username"] == email


def test_duplicate_external_invitation_preserves_original_member(portal, monkeypatch):
    """Cognitoで既存のメールアドレスを再招待すると競合を通知し、既存アカウントを削除しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.admin_create_user.side_effect = client.exceptions.UsernameExistsException(
        {"Error": {"Code": "UsernameExistsException", "Message": "User already exists"}},
        "AdminCreateUser",
    )
    invitation = {
        "full_name": "試験 花子",
        "email": "member@example.com",
        "role": "consumer",
        "project": "finance",
    }
    response = portal.post("/api/members", headers=admin, json=invitation)
    assert response.status_code == 409, response.json()
    assert response.json()["detail"]
    client.admin_delete_user.assert_not_called()


def test_directory_temporarily_unavailable(portal, monkeypatch):
    """外部名簿が一時的に利用できなければ一覧APIはサービス障害を返し、復旧後に同じページを読める。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.list_users.side_effect = [
        client.exceptions.InternalErrorException(
            {"Error": {"Code": "InternalErrorException", "Message": "Temporary failure"}}, "ListUsers"
        ),
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
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Group unavailable"}},
            "AdminAddUserToGroup",
        ),
        {},
    ]
    invitation = {"full_name": "試験 花子", "email": email, "project": "finance", "role": "consumer"}
    failed = portal.post("/api/members", headers=admin, json=invitation)
    assert 400 <= failed.status_code < 600 and failed.json()["detail"]
    client.admin_delete_user.assert_called_once_with(UserPoolId="test-pool", Username=email)
    retried = portal.post("/api/members", headers=admin, json=invitation)
    assert retried.status_code == 201
    assert retried.json()["subject"] == "retry-person"


def test_external_directory_source_for_membership(portal, monkeypatch):
    """Cognitoで登録した人を部署に所属させると、その識別子・ログイン名・役職で名簿を更新できる。"""
    admin = headers(portal, "admin")
    unit = portal.put(
        "/api/workspace/units/field", headers=admin, json={"name": "現場", "kind": "department"}
    )
    assert unit.status_code == 200
    client = _directory(monkeypatch)
    person = _external_member("field@example.com", "field-staff")
    client.list_users.return_value = {"Users": [person]}
    client.admin_get_user.return_value = {
        "Username": person["Username"],
        "UserAttributes": person["Attributes"],
        "Enabled": True,
    }
    listing = portal.get("/api/members", headers=admin)
    assert listing.status_code == 200
    assert any(
        row["subject"] == "field-staff" and row["username"] == person["Username"]
        for row in listing.json()["items"]
    )
    added = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": "field-staff", "unit_id": "field", "leader": True, "title": "現場監督"},
    )
    assert added.status_code == 200, added.json()
    usage = portal.get("/api/workspace/units/field/usage", headers=admin)
    assert usage.status_code == 200
    members = usage.json()["members"]
    assert any(
        row["subject"] == "field-staff" and row["title"] == "現場監督" and row["leader"]
        for row in members
    )
    removed = portal.delete(
        "/api/workspace/memberships",
        headers=admin,
        params={"subject": "field-staff", "unit_id": "field"},
    )
    assert removed.status_code == 200 and removed.json()["removed"]


def test_unknown_cognito_member_cannot_be_assigned(portal, monkeypatch):
    """名簿に該当する利用者がいない場合は、組織への所属を作成しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    client.list_users.return_value = {"Users": []}
    client.admin_get_user.side_effect = client.exceptions.UserNotFoundException(
        {"Error": {"Code": "UserNotFoundException", "Message": "No such user"}},
        "AdminGetUser",
    )
    failed = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": "former-staff", "unit_id": "finance"},
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
        "/api/members",
        headers=admin,
        json={
            "full_name": "試験 花子",
            "email": member["Username"],
            "role": "provider",
            "project": "supply",
        },
    )
    assert invited.status_code == 201
    client.admin_get_user.side_effect = client.exceptions.UserNotFoundException(
        {"Error": {"Code": "UserNotFoundException", "Message": "Retired"}},
        "AdminGetUser",
    )
    url = f"/api/members/{invited.json()['subject']}/profile"
    missing = portal.patch(url, headers=admin, json={"revision": 0, "display_name": "新名称"})
    assert missing.status_code == 404 and missing.json()["detail"]


def test_account_creation_outage_can_be_retried(portal, monkeypatch):
    """招待先のアカウントをまだ作成できなかった場合、復旧後に同じ内容で招待を完了できる。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "recovered@example.com"
    person = _external_member(email, "recovered")
    client.admin_create_user.side_effect = [
        client.exceptions.InternalErrorException(
            {"Error": {"Code": "InternalErrorException", "Message": "Temporary outage"}},
            "AdminCreateUser",
        ),
        {"User": person},
    ]
    data = {"full_name": "試験 花子", "email": email, "project": "finance", "role": "consumer"}
    unavailable = portal.post("/api/members", headers=admin, json=data)
    assert unavailable.status_code == 503 and unavailable.json()["detail"]
    client.admin_add_user_to_group.assert_not_called()
    recovered = portal.post("/api/members", headers=admin, json=data)
    assert recovered.status_code == 201 and recovered.json()["subject"] == "recovered"


def test_external_and_locally_retired_members_listed_by_subject(portal, monkeypatch):
    """退会した人と同じメールで別の利用者が登録されても、以前の氏名や表示名を引き継がない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "planning@example.com"
    old = _external_member(email, "previous-person")
    new = _external_member(email, "different-person")
    client.admin_create_user.return_value = {"User": old}
    client.admin_get_user.return_value = {
        "Username": email,
        "Enabled": True,
        "UserAttributes": old["Attributes"],
    }
    data = {
        "email": email,
        "project": "finance",
        "role": "consumer",
        "full_name": "以前の人",
        "display_name": "前任",
    }
    added = portal.post("/api/members", headers=admin, json=data)
    assert added.status_code == 201
    retired = portal.delete("/api/members/previous-person", headers=admin, params={"username": email})
    assert retired.status_code == 200 and retired.json()["deleted"]
    client.list_users.return_value = {"Users": [new]}
    listed = portal.get("/api/members", headers=admin)
    assert listed.status_code == 200
    current = next(row for row in listed.json()["items"] if row["subject"] == "different-person")
    assert current["username"] == email
    assert not current["deleted"] and current["full_name"] is None and current["display_name"] is None


def test_removed_cognito_group_member_stays_retired(portal, monkeypatch):
    """外部名簿の退会処理後は、その利用者を組織の有効な所属として表示しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    person = _external_member("leaving@example.com", "leaving-user")
    client.admin_create_user.return_value = {"User": person}
    client.admin_get_user.return_value = {
        "Username": person["Username"],
        "Enabled": True,
        "UserAttributes": person["Attributes"],
    }
    invited = portal.post(
        "/api/members",
        headers=admin,
        json={
            "full_name": "試験 花子",
            "email": person["Username"],
            "project": "finance",
            "role": "consumer",
        },
    )
    assert invited.status_code == 201
    deleted = portal.delete(
        "/api/members/leaving-user", headers=admin, params={"username": person["Username"]}
    )
    assert deleted.status_code == 200
    known = portal.get("/api/workspace", headers=admin).json()["memberships"]
    assert not any(row["subject"] == "leaving-user" and row.get("active", True) for row in known)


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            "TooManyRequestsException",
            id="throttled",
            marks=pytest.mark.case_detail("外部名簿の一時的な流量制限を503で返す"),
        ),
        pytest.param(
            "connection",
            id="disconnected",
            marks=pytest.mark.case_detail("名簿サービスへの接続が途切れても同じページを再取得できる"),
        ),
    ],
)
def test_external_list_recovers_from_transient_errors(portal, monkeypatch, failure):
    """外部名簿との通信・流量制限で一覧が取れない場合は、一時障害を示し、復旧後に再取得できる。"""
    from botocore.exceptions import EndpointConnectionError

    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    if failure == "connection":
        error = EndpointConnectionError(endpoint_url="https://directory.example.invalid")
    else:
        error = client.exceptions.TooManyRequestsException(
            {"Error": {"Code": failure, "Message": "Try later"}},
            "ListUsers",
        )
    client.list_users.side_effect = [
        error,
        {"Users": [_external_member("returning@example.com", "returning")]},
    ]
    waiting = portal.get("/api/members", headers=admin, params={"limit": 5})
    assert waiting.status_code == 503 and waiting.json()["detail"]
    retrieved = portal.get("/api/members", headers=admin, params={"limit": 5})
    assert retrieved.status_code == 200
    assert [row["subject"] for row in retrieved.json()["items"]] == ["returning"]


def test_disabled_external_user_is_not_assignable(portal, monkeypatch):
    """外部名簿で無効になった利用者を所属に追加しようとしても、有効な所属を作成しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    account = {**_external_member("former@example.com", "former"), "Enabled": False}
    client.list_users.return_value = {"Users": [account]}
    client.admin_get_user.return_value = {
        "Username": account["Username"],
        "UserAttributes": account["Attributes"],
        "Enabled": False,
    }
    added = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": "former", "unit_id": "finance", "title": "スタッフ"},
    )
    assert added.status_code in (404, 409) and added.json()["detail"]
    directory = portal.get("/api/workspace", headers=admin).json()
    assert not any(
        row["subject"] == "former" and row.get("active", True) for row in directory["memberships"]
    )


def test_external_username_lookup_keeps_distinct_subjects(portal, monkeypatch):
    """再利用されたログイン名の現在の識別子が異なる場合、以前の会員としてプロフィールを変更しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "former-staff@example.com"
    old = _external_member(email, "past-staff")
    new = _external_member(email, "current-staff")
    client.admin_create_user.return_value = {"User": old}
    created = portal.post(
        "/api/members",
        headers=admin,
        json={"full_name": "試験 花子", "email": email, "project": "finance", "role": "consumer"},
    )
    assert created.status_code == 201
    client.admin_get_user.return_value = {
        "Username": email,
        "Enabled": True,
        "UserAttributes": new["Attributes"],
    }
    attempt = portal.patch(
        "/api/members/past-staff/profile", headers=admin, json={"revision": 0, "display_name": "旧名"}
    )
    assert attempt.status_code in (404, 409) and attempt.json()["detail"]
    client.list_users.return_value = {"Users": [new]}
    members = portal.get("/api/members", headers=admin).json()["items"]
    assert all(item["display_name"] != "旧名" for item in members if item["subject"] == "current-staff")


def test_invitation_to_portal_project_without_external_group(portal, monkeypatch):
    """ポータルで新設したプロジェクトへ招待すると、外部グループの設定がなくても所属が作られる。"""
    admin = headers(portal, "admin")
    created = portal.put(
        "/api/workspace/units/portal-team", headers=admin, json={"kind": "project", "name": "新設"}
    )
    assert created.status_code == 200
    client = _directory(monkeypatch)
    account = _external_member("portal-only@example.com", "portal-staff")
    client.admin_create_user.return_value = {"User": account}
    result = portal.post(
        "/api/members",
        headers=admin,
        json={
            "full_name": "試験 花子",
            "email": account["Username"],
            "project": "portal-team",
            "role": "consumer",
        },
    )
    assert result.status_code == 201 and result.json()["subject"] == "portal-staff"
    client.admin_add_user_to_group.assert_not_called()
    members = portal.get("/api/workspace/units/portal-team/usage", headers=admin).json()["members"]
    assert any(member["subject"] == "portal-staff" and member.get("active", True) for member in members)


def test_retirement_retry_after_remote_account_has_gone(portal, monkeypatch):
    """外部のアカウントが消えた後に退会操作を繰り返しても、ポータルの会員資格は復活しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    account = _external_member("finished@example.com", "finished")
    client.admin_create_user.return_value = {"User": account}
    client.admin_get_user.return_value = {
        "Username": account["Username"],
        "Enabled": True,
        "UserAttributes": account["Attributes"],
    }
    assert (
        portal.post(
            "/api/members",
            headers=admin,
            json={
                "full_name": "試験 花子",
                "email": account["Username"],
                "project": "finance",
                "role": "provider",
            },
        ).status_code
        == 201
    )
    url = "/api/members/finished"
    params = {"username": account["Username"]}
    first = portal.delete(url, headers=admin, params=params)
    assert first.status_code == 200 and first.json()["deleted"]
    missing = client.exceptions.UserNotFoundException(
        {"Error": {"Code": "UserNotFoundException", "Message": "No such account"}},
        "AdminGetUser",
    )
    client.admin_get_user.side_effect = missing
    client.admin_delete_user.side_effect = missing
    client.list_users.return_value = {"Users": []}
    repeated = portal.delete(url, headers=admin, params=params)
    assert repeated.status_code in (200, 404)
    listing = portal.get("/api/members", headers=admin).json()["items"]
    assert not any(member["subject"] == "finished" and not member["deleted"] for member in listing)
    groups = portal.get("/api/workspace", headers=admin).json()["memberships"]
    assert not any(row["subject"] == "finished" and row.get("active", True) for row in groups)


def test_retirement_does_not_delete_replacement_username(portal, monkeypatch):
    """以前の人と同じログイン名に別の識別子が割り当てられた場合、退会操作で後任を削除しない。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    email = "same-name@example.com"
    previous = _external_member(email, "first-person")
    replacement = _external_member(email, "second-person")
    client.admin_create_user.return_value = {"User": previous}
    assert (
        portal.post(
            "/api/members",
            headers=admin,
            json={"full_name": "試験 花子", "email": email, "role": "consumer", "project": "finance"},
        ).status_code
        == 201
    )
    client.admin_get_user.return_value = {
        "Username": email,
        "Enabled": True,
        "UserAttributes": replacement["Attributes"],
    }
    removed = portal.delete("/api/members/first-person", headers=admin, params={"username": email})
    assert removed.status_code in (404, 409) and removed.json()["detail"]
    client.admin_delete_user.assert_not_called()


def test_external_only_member_can_retire(portal, monkeypatch):
    """Cognito名簿から選んだ外部登録の利用者も、管理者が識別子とログイン名を照合して退会させられる。"""
    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    member = _external_member("outside@example.com", "outside")
    client.list_users.return_value = {"Users": [member]}
    client.admin_get_user.return_value = {
        "Username": member["Username"],
        "Enabled": True,
        "UserAttributes": member["Attributes"],
    }
    listing = portal.get("/api/members", headers=admin).json()["items"]
    external = next(row for row in listing if row["subject"] == "outside")
    retired = portal.delete(
        f"/api/members/{external['subject']}", headers=admin, params={"username": external["username"]}
    )
    assert retired.status_code == 200 and retired.json()["deleted"]
    client.admin_delete_user.assert_called_once_with(UserPoolId="test-pool", Username=member["Username"])


def test_invitation_with_unavailable_project_does_not_create_external_account(portal, monkeypatch):
    """招待画面を開いてから対象プロジェクトが廃止されたとき、外部名簿に宛先だけの人を残さない。"""
    admin = headers(portal, "admin")
    key = "old-project"
    assert (
        portal.put(
            f"/api/workspace/units/{key}", headers=admin, json={"kind": "project", "name": "旧部門"}
        ).status_code
        == 200
    )
    assert portal.delete(f"/api/workspace/units/{key}", headers=admin).status_code == 200
    client = _directory(monkeypatch)
    denied = portal.post(
        "/api/members",
        headers=admin,
        json={"full_name": "試験 花子", "email": "late@example.com", "role": "consumer", "project": key},
    )
    assert denied.status_code in (404, 409, 422) and denied.json()["detail"]
    client.admin_create_user.assert_not_called()


def test_incomplete_external_invitation_reports_required_recovery(portal, monkeypatch, caplog):
    """招待のロール付与と後片付けがともに失敗したら、復旧対象を運用担当者がログから確認できる。"""
    import json

    admin = headers(portal, "admin")
    client = _directory(monkeypatch)
    member = _external_member("recover@example.com", "recover-subject")
    client.admin_create_user.return_value = {"User": member}
    for method, operation in (
        (client.admin_add_user_to_group, "AdminAddUserToGroup"),
        (client.admin_delete_user, "AdminDeleteUser"),
    ):
        method.side_effect = client.exceptions.InternalErrorException(
            {"Error": {"Code": "InternalErrorException", "Message": "Temporary outage"}},
            operation,
        )
    response = portal.post(
        "/api/members",
        headers=admin,
        json={
            "full_name": "試験 花子",
            "email": member["Username"],
            "role": "consumer",
            "project": "finance",
        },
    )
    assert response.status_code == 503 and response.json()["detail"]
    items = [json.loads(record.message) for record in caplog.records if record.message.startswith("{")]
    recovery = [item for item in items if item.get("level") == "CRITICAL"]
    assert any(item.get("operator_action") for item in recovery)


def test_external_admin_handover(portal, monkeypatch):
    """既存の管理者を全ページから引き継ぎ、同じメールでも識別子が異なる利用者には付与しない。"""
    token = headers(portal, "admin")
    client = _directory(monkeypatch)
    old = _external_member("initial-admin", "admin")
    second = _external_member("other@example.test", "other")
    person = _external_member("target@example.test", "target")
    client.list_users.return_value = {"Users": [person]}
    client.admin_get_user.return_value = {"Enabled": True, "UserAttributes": person["Attributes"]}
    url = "/api/members/target/admin-role"
    client.list_users_in_group.side_effect = [
        client.exceptions.InternalErrorException(
            {"Error": {"Code": "InternalErrorException"}}, "ListUsersInGroup"
        ),
        {"Users": [old], "NextToken": "more"},
        {"Users": [second]},
    ]
    assert portal.put(url, headers=token, json={"admin": True}).status_code == 503
    portal.put(url, headers=token, json={"admin": True}).raise_for_status()
    assert client.list_users_in_group.call_args.kwargs["NextToken"] == "more"
    client.list_users.return_value = {"Users": [old, second, person]}
    assert all(m["admin"] for m in portal.get("/api/members", headers=token).json()["items"])
    client.admin_get_user.return_value = {"Enabled": True, "UserAttributes": second["Attributes"]}
    assert portal.put(url, headers=token, json={"admin": False}).status_code == 404
