# 利用者が選ぶ認証方式・利用範囲・期限を、発行、更新、失効の公開手順で検証する。
import pytest

from tests.support.catalog import approved, headers


@pytest.mark.parametrize(
    "mode, kind, explicit_assets",
    [
        pytest.param(
            "bearer",
            "personal",
            False,
            id="bearer-all",
            marks=pytest.mark.case_detail("本人の短期Bearerで承認済みAPI全体を呼べる"),
        ),
        pytest.param(
            "bearer",
            "shared",
            True,
            id="bearer-project",
            marks=pytest.mark.case_detail("共有の短期Bearerを指定のAPIで利用できる"),
        ),
        pytest.param(
            "app",
            "personal",
            True,
            id="app-personal",
            marks=pytest.mark.case_detail("アプリと本人の資格で指定のAPIを利用できる"),
        ),
        pytest.param(
            "app",
            "shared",
            True,
            id="app-for-members",
            marks=pytest.mark.case_detail("共有アプリで指定したメンバーが承認済み操作を利用できる"),
        ),
        pytest.param(
            "system",
            "shared",
            False,
            id="system-project",
            marks=pytest.mark.case_detail(
                "プロジェクトのリーダーがシステム認証を発行し、利用者のログインなしで交換できる"
            ),
        ),
    ],
)
def test_issue_use_and_retire_credentials(portal, mode, kind, explicit_assets):
    """認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    asset_id, _, invoke_url = approved(portal, owner, user)
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assigned = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": subject, "unit_id": "finance", "leader": True},
    )
    assert assigned.status_code == 200
    credential = {
        "project": "finance",
        "name": "月次確認",
        "kind": kind,
        "mode": mode,
        "ttl_minutes": 12,
        "refresh_minutes": 4,
    }
    if explicit_assets:
        credential["api_ids"] = [asset_id]
    if mode == "app":
        options = portal.get(
            "/api/credentials/options", headers=user, params={"project": "finance"}
        ).json()
        asset = next(a for a in options["assets"] if a["id"] == asset_id)
        credential["operations"] = {asset_id: asset["operations"]}
        credential["users"] = [subject]
    issued = portal.post("/api/credentials", headers=user, json=credential)
    assert issued.status_code == 201
    item = issued.json()
    key_id = item["id"]
    assert item["project"] == "finance" and item["kind"] == kind and item["mode"] == mode
    if mode == "bearer":
        token = item
    else:
        exchange = {"client_id": item["client_id"], "client_secret": item["client_secret"]}
        exchange_headers = user if mode == "app" else {}
        token_result = portal.post("/api/auth/token", headers=exchange_headers, json=exchange)
        assert token_result.status_code == 200
        token = token_result.json()
    assert token["token_type"] == "Bearer" and 0 < token["expires_in"] <= 720
    assert 0 < token["refresh_after"] <= 240 and token["refresh_at"] < token["expires_at"]
    assert (
        portal.get(invoke_url, headers={"Authorization": f"Bearer {token['access_token']}"}).status_code
        == 200
    )
    if mode in ("app", "system"):
        rotated = portal.post(f"/api/credentials/{key_id}/rotate", headers=user)
        assert rotated.status_code == 200
        assert rotated.json()["client_secret"] != item["client_secret"]
        updated_token = portal.post("/api/auth/token", headers=exchange_headers, json=rotated.json())
        assert updated_token.status_code == 200 and updated_token.json()["access_token"]
    retired = portal.delete(f"/api/keys/{key_id}", headers=user)
    assert retired.status_code == 200 and retired.json()["revoked"]
    keys = portal.get("/api/keys", headers=user).json()
    assert any(key["id"] == key_id and key["revoked"] for key in keys)


def test_choose_shortest_scope_limit(portal):
    """提供APIが複数あるとき、選んだ対象と利用プロジェクトのうち短い上限が発行条件に反映される。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    asset_id, _, _ = approved(portal, owner, user)
    for scope, key, minutes, actor in (("units", "finance", 30, admin), ("apis", asset_id, 9, owner)):
        configured = portal.put(
            f"/api/credential-limits/{scope}/{key}", headers=actor, json={"max_minutes": minutes}
        )
        assert configured.status_code == 200 and configured.json()["max_minutes"] == minutes
    options = portal.get("/api/credentials/options", headers=user, params={"project": "finance"}).json()
    asset = next(a for a in options["assets"] if a["id"] == asset_id)
    assert asset["max_minutes"] == 9
    draft = {
        "project": "finance",
        "name": "照会",
        "mode": "bearer",
        "kind": "personal",
        "api_ids": [asset_id],
        "ttl_minutes": 9,
        "refresh_minutes": 6,
    }
    issued = portal.post("/api/credentials", headers=user, json=draft)
    assert issued.status_code == 201 and issued.json()["expires_in"] <= 540


@pytest.mark.parametrize(
    "edits",
    [
        pytest.param(
            {"refresh_minutes": 11},
            id="refresh-after-expiry",
            marks=pytest.mark.case_detail("有効期間後の時刻を更新開始に選べない"),
        ),
        pytest.param(
            {"api_ids": ["retired-product"]},
            id="retired-product",
            marks=pytest.mark.case_detail("既に提供終了したAPIを対象として発行しない"),
        ),
        pytest.param(
            {"operations": {"available": ["GET /removed"]}},
            id="removed-operation",
            marks=pytest.mark.case_detail("APIに存在しない操作は選んで発行できない"),
        ),
        pytest.param(
            {"users": ["former-member"]},
            id="departed-member",
            marks=pytest.mark.case_detail(
                "プロジェクトに所属しない利用者を対象にしたアプリ設定を保存しない"
            ),
        ),
    ],
)
def test_invalid_issuance_keeps_project_credentials(portal, edits):
    """発行条件に一致しない設定で認証情報を発行できず、既存の認証情報一覧を維持する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    asset_id, _, _ = approved(portal, owner, user)
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": "finance", "leader": True},
        ).status_code
        == 200
    )
    before = portal.get("/api/keys", headers=user).json()
    draft = {
        "project": "finance",
        "name": "月末集計",
        "mode": "app",
        "kind": "shared",
        "api_ids": [asset_id],
        "ttl_minutes": 10,
        "refresh_minutes": 5,
        **edits,
    }
    if "operations" in edits:
        draft["operations"] = {asset_id: edits["operations"]["available"]}
    denied = portal.post("/api/credentials", headers=user, json=draft)
    assert denied.status_code in (403, 422) and denied.json()["detail"]
    assert portal.get("/api/keys", headers=user).json() == before


def test_portal_bearer_refresh_and_scope_after_renewal(portal):
    """短期Bearerをポータルで更新しても認証情報は増えず、指定のAPIと有効期間を維持する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    draft = {
        "project": "finance",
        "name": "日報",
        "mode": "bearer",
        "kind": "personal",
        "api_ids": [asset_id],
        "ttl_minutes": 8,
        "refresh_minutes": 2,
    }
    issued = portal.post("/api/credentials", headers=user, json=draft)
    assert issued.status_code == 201
    credential_id = issued.json()["id"]
    refreshed = portal.post(f"/api/credentials/{credential_id}/token", headers=user)
    assert refreshed.status_code == 200
    token = refreshed.json()
    assert token["token_type"] == "Bearer" and 0 < token["expires_in"] <= 480
    assert 0 < token["refresh_after"] <= 120
    call = portal.get(invoke_url, headers={"Authorization": f"Bearer {token['access_token']}"})
    assert call.status_code == 200
    listing = portal.get("/api/keys", headers=user).json()
    assert [key["id"] for key in listing if key["name"] == "日報"] == [credential_id]


def test_project_with_no_approvals_can_see_empty_options(portal):
    """新設プロジェクトのメンバーには本人が選べる認証情報と、承認待ちで空の対象API一覧を示す。"""
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/units/new-team", headers=admin, json={"kind": "project", "name": "新事業"}
        ).status_code
        == 200
    )
    for leader in (False, True):
        assigned = portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": "new-team", "leader": leader},
        )
        assert assigned.status_code == 200
        options = portal.get(
            "/api/credentials/options", headers=user, params={"project": "new-team"}
        ).json()
        assert options["assets"] == [] and options["may_manage"] is leader
        assert any(member["subject"] == subject for member in options["members"])


@pytest.mark.parametrize(
    "kind, selected",
    [
        pytest.param(
            "shared",
            False,
            id="all-approved",
            marks=pytest.mark.case_detail("共有キーでプロジェクトの承認済みAPI全体を選べる"),
        ),
        pytest.param(
            "personal",
            True,
            id="specific-api",
            marks=pytest.mark.case_detail("本人限定キーで指定したAPIを選べる"),
        ),
    ],
)
def test_legacy_credential_inventory_and_independent_revocation(portal, kind, selected):
    """従来キーを複数発行し、一つを失効させても同じプロジェクトの別のキーで利用を続けられる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    available = portal.get("/api/key-assets", headers=user)
    assert available.status_code == 200 and any(asset["id"] == asset_id for asset in available.json())
    payload = {"project": "finance", "kind": kind, "api_ids": [asset_id] if selected else []}
    issued = []
    for name in ("経理01", "経理02"):
        response = portal.post("/api/keys", headers=user, json={**payload, "name": name})
        assert response.status_code == 201
        issued.append(response.json())
    first, second = issued
    assert first["id"] != second["id"] and first["secret"] != second["secret"]
    assert portal.delete(f"/api/keys/{first['id']}", headers=user).json()["revoked"]
    keys = {item["id"]: item for item in portal.get("/api/keys", headers=user).json()}
    assert keys[first["id"]]["revoked"] and not keys[second["id"]]["revoked"]
    assert keys[second["id"]]["api_ids"] == payload["api_ids"]
    caller = {"Authorization": f"Bearer {second['secret']}"}
    if kind == "personal":
        caller = {**user, "X-API-Key": second["secret"]}
    assert portal.get(invoke_url, headers=caller).status_code == 200


def test_shortened_api_limit_requires_shorter_credential(portal):
    """提供者が対象APIの有効期間を縮めると、長すぎる発行条件を拒み、新しい上限以内の発行を許可する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, _ = approved(portal, owner, user)
    configured = portal.put(
        f"/api/credential-limits/apis/{asset_id}", headers=owner, json={"max_minutes": 4}
    )
    assert configured.status_code == 200 and configured.json()["max_minutes"] == 4
    draft = {
        "project": "finance",
        "name": "短期照会",
        "kind": "personal",
        "mode": "bearer",
        "ttl_minutes": 5,
        "refresh_minutes": 2,
        "api_ids": [asset_id],
    }
    old = portal.post("/api/credentials", headers=user, json=draft)
    assert old.status_code == 422 and old.json()["detail"]
    accepted = portal.post("/api/credentials", headers=user, json={**draft, "ttl_minutes": 4})
    assert accepted.status_code == 201 and 0 < accepted.json()["expires_in"] <= 240


def test_revoked_grant_applies_to_refreshed_bearer(portal):
    """承認されたAPIを呼び出せた本人も、権利の取消後はトークンを更新してもそのAPIを実行できない。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    issued = portal.post(
        "/api/credentials",
        headers=user,
        json={
            "mode": "bearer",
            "kind": "personal",
            "project": "finance",
            "name": "集計",
            "api_ids": [asset_id],
        },
    )
    assert issued.status_code == 201
    caller = {"Authorization": f"Bearer {issued.json()['access_token']}"}
    assert portal.get(invoke_url, headers=caller).status_code == 200
    own = portal.get("/api/requests", headers=user, params={"asset_id": asset_id}).json()
    approved_right = next(r for r in own if r["project"] == "finance" and r["status"] == "approved")
    revoked = portal.post(
        f"/api/requests/{approved_right['id']}",
        headers=owner,
        json={"revision": approved_right["revision"], "action": "revoke", "reason": "利用終了"},
    )
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert portal.get(invoke_url, headers=caller).status_code == 403
    refreshed = portal.post(f"/api/credentials/{issued.json()['id']}/token", headers=user)
    assert refreshed.status_code == 200
    renewed = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    assert portal.get(invoke_url, headers=renewed).status_code == 403


@pytest.mark.parametrize(
    "specify_type",
    [
        pytest.param(
            False,
            id="default-token-type",
            marks=pytest.mark.case_detail("希望するトークン種別を省略して短期Bearerを取得する"),
        ),
        pytest.param(
            True,
            id="explicit-token-type",
            marks=pytest.mark.case_detail(
                "アクセストークンを指定してOAuth交換したあとも直前のトークンを利用できる"
            ),
        ),
    ],
)
def test_oauth_exchange_keeps_original_token_valid(portal, specify_type):
    """API Docsで本人のログインを短期Bearerに交換し、元の期限までは直前のトークンでも呼び出せる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    issued = portal.post(
        "/api/credentials",
        headers=user,
        json={
            "name": "Docsから照会",
            "kind": "personal",
            "mode": "bearer",
            "project": "finance",
            "api_ids": [asset_id],
        },
    )
    assert issued.status_code == 201
    credential = issued.json()
    token_type = "urn:ietf:params:oauth:token-type:access_token"
    form = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token_type": token_type,
        "subject_token": user["Authorization"].removeprefix("Bearer "),
    }
    if specify_type:
        form["requested_token_type"] = token_type
    exchanged = portal.post(f"/api/credentials/{credential['id']}/token-exchange", data=form)
    assert exchanged.status_code == 200
    result = exchanged.json()
    assert result["issued_token_type"] == token_type and result["token_type"] == "Bearer"
    for access_token in (credential["access_token"], result["access_token"]):
        invoked = portal.get(invoke_url, headers={"Authorization": f"Bearer {access_token}"})
        assert invoked.status_code == 200 and invoked.headers["x-request-id"]


def test_whole_project_and_individual_inventories(portal):
    """個人と共有の両方で認証情報を発行すると、共有のメンバーと本人がそれぞれの範囲を確認できる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    asset_id, _, _ = approved(portal, owner, user)
    subject = portal.get("/api/me", headers=owner).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": "finance", "leader": True},
        ).status_code
        == 200
    )
    keys = {}
    for kind in ("shared", "personal"):
        created = portal.post(
            "/api/keys",
            headers=user,
            json={"name": kind, "project": "finance", "kind": kind, "api_ids": [asset_id]},
        )
        assert created.status_code == 201
        keys[kind] = created.json()["id"]
    own = portal.get("/api/keys", headers=user).json()
    assert set(keys.values()) <= {key["id"] for key in own}
    inventory = portal.get("/api/keys", headers=owner).json()
    assert any(k["id"] == keys["shared"] and k["kind"] == "shared" for k in inventory)


def test_shorter_project_cap_rejects_invalid_refresh(portal):
    """組織で定めた上限を守って発行し、更新開始時刻は指定した有効期間の中に限定する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    asset_id, _, _ = approved(portal, owner, user)
    assert (
        portal.put(
            "/api/credential-limits/units/finance", headers=admin, json={"max_minutes": 1}
        ).status_code
        == 200
    )
    body = {
        "mode": "bearer",
        "kind": "personal",
        "project": "finance",
        "name": "短時間処理",
        "api_ids": [asset_id],
        "ttl_minutes": 1,
    }
    refused = portal.post("/api/credentials", headers=user, json={**body, "refresh_minutes": 2})
    assert refused.status_code == 422
    issued = portal.post("/api/credentials", headers=user, json=body)
    assert issued.status_code == 201
    assert 0 < issued.json()["expires_in"] <= 60 and 0 < issued.json()["refresh_after"] <= 60


def test_project_leader_takes_over_shared_system_credential(portal):
    """後任のプロジェクトリーダーは共有システム認証のシークレットを更新し、同じ資格名で継続運用できる。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    asset_id, _, invoke_url = approved(portal, owner, user)
    subjects = {}
    for persona, actor in (("outgoing", user), ("incoming", owner)):
        subjects[persona] = portal.get("/api/me", headers=actor).json()["subject"]
    for name, leader in (("outgoing", True), ("incoming", False)):
        assert (
            portal.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"subject": subjects[name], "unit_id": "finance", "leader": leader},
            ).status_code
            == 200
        )
    issued = portal.post(
        "/api/credentials",
        headers=user,
        json={
            "project": "finance",
            "kind": "shared",
            "mode": "system",
            "name": "月次バッチ",
            "api_ids": [asset_id],
        },
    )
    assert issued.status_code == 201
    for name, leader in (("incoming", True), ("outgoing", False)):
        assert (
            portal.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"subject": subjects[name], "unit_id": "finance", "leader": leader},
            ).status_code
            == 200
        )
    key_id = issued.json()["id"]
    rotated = portal.post(f"/api/credentials/{key_id}/rotate", headers=owner)
    assert rotated.status_code == 200
    assert rotated.json()["client_secret"] != issued.json()["client_secret"]
    token = portal.post("/api/auth/token", json=rotated.json())
    assert token.status_code == 200
    assert (
        portal.get(
            invoke_url, headers={"Authorization": f"Bearer {token.json()['access_token']}"}
        ).status_code
        == 200
    )
    current = portal.get("/api/keys", headers=owner).json()
    assert [(k["id"], k["name"]) for k in current if k["id"] == key_id] == [(key_id, "月次バッチ")]
