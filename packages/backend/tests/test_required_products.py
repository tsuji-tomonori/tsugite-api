"""商品提供者と申請者が、環境別の条件・申請結果・公開版を追跡できることを確認する。"""

from copy import deepcopy

import pytest

from tests.support.catalog import headers, publish_asset


def _draft():
    return {
        "owner": "supply",
        "name": "配送日照会",
        "summary": "出荷日を調べる",
        "slug": "delivery-calendar",
        "targets": {"sandbox": "sample-sandbox"},
        "spec": {
            "openapi": "3.1.0",
            "info": {"title": "配送", "version": "1.0"},
            "paths": {"/days": {"get": {"responses": {"200": {"description": "配送日"}}}}},
        },
    }


def _register(portal, owner, product):
    created = portal.post("/api/apis", headers=owner, json=product)
    assert created.status_code == 201
    url = f"/api/apis/{created.json()['id']}"
    published = publish_asset(portal, f"{url}", owner)
    assert published.status_code == 200 and published.json()["published"]
    return url


def test_automatic_offer_requires_terms_and_registered_answer(portal):
    """自動承認の環境でも規約と必須の回答を確認し、受理した同意と回答を申請に保存する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    terms = "検証用データにのみ使用します。"
    label = "実施番号"
    draft["offers"] = {
        "sandbox": {
            "instructions": "実施番号を入力してください。",
            "terms": terms,
            "route": "auto",
            "fields": [{"label": label, "required": True, "allowed_values": ["TEST-07"]}],
        }
    }
    url = _register(portal, owner, draft)
    offer = portal.get(url, headers=user).json()["offers"]["sandbox"]
    assert (
        offer["terms"] == terms and offer["instructions"] == draft["offers"]["sandbox"]["instructions"]
    )
    application = {
        "project": "finance",
        "environment": "sandbox",
        "reason": "検証",
        "offer_version": offer["version"],
        "answers": {label: "TEST-07"},
        "terms_accepted": True,
    }
    for correction in ({"terms_accepted": False}, {"answers": {}}, {"answers": {label: "未登録"}}):
        refused = portal.post(f"{url}/requests", headers=user, json={**application, **correction})
        assert refused.status_code == 422
    accepted = portal.post(f"{url}/requests", headers=user, json=application)
    assert accepted.status_code == 201
    right = accepted.json()
    assert right["status"] == "approved"
    evidence = right["application"]
    assert evidence["terms"] == terms and evidence["terms_accepted"]
    assert evidence["version"] == offer["version"] and evidence["answers"] == {label: "TEST-07"}


@pytest.mark.parametrize(
    "personal, action, status",
    [
        pytest.param(
            False,
            "reject",
            "rejected",
            id="team-rejection",
            marks=pytest.mark.case_detail(
                "提供者がプロジェクトの申請を却下すると理由が残り再申請できる"
            ),
        ),
        pytest.param(
            True,
            "withdraw",
            "withdrawn",
            id="individual-withdrawal",
            marks=pytest.mark.case_detail("申請者が本人の申請を取り下げると理由が残り再申請できる"),
        ),
    ],
)
def test_request_decision_and_reapplication(portal, personal, action, status):
    """却下または取り下げの理由を本人が確認でき、同じ商品と環境に再申請できる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    url = _register(portal, owner, _draft())
    asset_id = url.rsplit("/", 1)[1]
    application = {
        "project": "finance",
        "environment": "sandbox",
        "reason": "初回の試験",
        "personal": personal,
    }
    submitted = portal.post(f"{url}/requests", headers=user, json=application)
    assert submitted.status_code == 201
    right = submitted.json()
    assert right["status"] == "pending" and right["reason"] == application["reason"]
    decision_url = f"/api/requests/{right['id']}"
    reason = "計画を見直してから再申請する"
    decision = {"revision": right["revision"], "action": action, "reason": reason}
    actor = user if personal else owner
    decided = portal.post(decision_url, headers=actor, json=decision)
    assert decided.status_code == 200
    assert decided.json()["status"] == status
    history = portal.get("/api/requests", headers=user, params={"asset_id": asset_id}).json()
    assert any(row["status"] == status and row["decision_reason"] == reason for row in history)
    resubmitted = portal.post(f"{url}/requests", headers=user, json={**application, "reason": "再試験"})
    assert resubmitted.status_code == 201
    assert resubmitted.json()["status"] == "pending" and resubmitted.json()["reason"] == "再試験"
    stale = portal.post(decision_url, headers=actor, json=decision)
    assert stale.status_code == 409
    history = portal.get("/api/requests", headers=user, params={"asset_id": asset_id}).json()
    assert any(row["status"] == "pending" and row["reason"] == "再試験" for row in history)


def test_spec_revision_and_release_history(portal):
    """操作の追加・変更・削除を含む仕様を再公開すると、利用者は版ごとの説明と差分を読める。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    draft["spec"]["paths"]["/old"] = deepcopy(draft["spec"]["paths"]["/days"])
    draft["release_note"] = "初版"
    url = _register(portal, owner, draft)
    original = portal.get(url, headers=user).json()
    draft["spec"]["info"]["version"] = "2.0"
    draft["spec"]["paths"]["/calendar"] = draft["spec"]["paths"].pop("/old")
    draft["spec"]["paths"]["/days"]["get"]["summary"] = "予約可能な配送日を取得"
    draft["release_note"] = "カレンダーを追加して旧照会を廃止"
    updated = portal.put(url, headers=owner, params={"revision": original["revision"]}, json=draft)
    assert updated.status_code == 200 and not updated.json()["published"]
    republished = publish_asset(portal, f"{url}", owner)
    assert republished.status_code == 200 and republished.json()["published"]
    history = portal.get(url, headers=user).json()["releases"]
    entries = {row["api_version"]: row for row in history}
    first, second = entries["1.0"], entries["2.0"]
    assert first["number"] < second["number"] and first["note"] == "初版"
    assert second["note"] == draft["release_note"] and second["openapi"] == "3.1.0"
    assert first["published_at"] and second["published_at"]
    for category, path in (("added", "/calendar"), ("removed", "/old"), ("changed", "/days")):
        assert any(path in item for item in second[category])


def test_project_transfer_with_established_usage(portal):
    """利用中のプロジェクトを移管すると、利用者の所属、商品の公開範囲、利用権と監視設定を引き継ぐ。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    for project in ("original", "successor"):
        created = portal.put(
            f"/api/workspace/units/{project}",
            headers=admin,
            json={"kind": "project", "name": project},
        )
        assert created.status_code == 200
    added = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": subject, "unit_id": "original", "leader": True},
    )
    assert added.status_code == 200
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": "auto"}}
    url = _register(portal, owner, draft)
    asset_id = url.rsplit("/", 1)[1]
    policy_url = f"{url}/policy"
    revision = portal.get(url, headers=owner).json()["revision"]
    result = portal.put(
        policy_url,
        headers=owner,
        params={"revision": revision},
        json={"visibility": "restricted", "projects": ["original"]},
    )
    assert result.status_code == 200, result.json()
    offer = portal.get(url, headers=user).json()["offers"]["sandbox"]
    requested = portal.post(
        f"{url}/requests",
        headers=user,
        json={
            "project": "original",
            "environment": "sandbox",
            "reason": "月次集計",
            "offer_version": offer["version"],
        },
    )
    assert requested.status_code == 201 and requested.json()["status"] == "approved"
    rule = {
        "asset_id": asset_id,
        "project": "original",
        "environment": "sandbox",
        "threshold": 54,
        "minutes": 60,
        "stop": False,
    }
    assert portal.put("/api/alerts", headers=owner, json=rule).status_code == 200
    assert (
        portal.put(
            "/api/credential-limits/units/original", headers=user, json={"max_minutes": 33}
        ).status_code
        == 200
    )
    assert portal.delete("/api/workspace/units/original", headers=admin).status_code == 409
    moved = portal.post(
        "/api/workspace/units/original/transfer", headers=admin, json={"destination": "successor"}
    )
    assert moved.status_code == 200, moved.json()
    profile = portal.get("/api/me", headers=user).json()
    assert "successor" in profile["projects"] and "original" not in profile["projects"]
    assert portal.get(policy_url, headers=owner).json()["projects"] == ["successor"]
    current = portal.get("/api/requests", headers=user, params={"asset_id": asset_id}).json()
    assert any(row["project"] == "successor" and row["status"] == "approved" for row in current)
    alerts = portal.get("/api/alerts", headers=owner).json()
    assert any(
        row["project"] == "successor" and row["asset_id"] == asset_id and row["threshold"] == 54
        for row in alerts
    )
    assert portal.get("/api/credential-limits/units/successor", headers=user).json()["max_minutes"] == 33


@pytest.mark.parametrize(
    "route",
    [
        pytest.param(
            "department_provider",
            id="department-then-provider",
            marks=pytest.mark.case_detail("所属部署の上位リーダーから提供者へ回す"),
        ),
        pytest.param(
            "custom",
            id="explicit-department",
            marks=pytest.mark.case_detail("指定部署のリーダーから提供者へ回す"),
        ),
    ],
)
def test_two_stage_review(portal, route):
    """部署リーダーの判断だけでは承認は終わらず、提供者の最終承認で両者の理由を確認できる。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    leader = headers(portal, "auditor")
    user = headers(portal, "consumer")
    for key, parent, actor, is_leader in (
        ("review-board", "", leader, True),
        ("staff", "review-board", user, False),
    ):
        unit = portal.put(
            f"/api/workspace/units/{key}",
            headers=admin,
            json={"kind": "department", "name": key, "parent": parent},
        )
        assert unit.status_code == 200
        subject = portal.get("/api/me", headers=actor).json()["subject"]
        added = portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": key, "leader": is_leader},
        )
        assert added.status_code == 200
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": route}}
    if route == "custom":
        draft["offers"]["sandbox"]["steps"] = ["unit/review-board", "provider"]
    url = _register(portal, owner, draft)
    offer = portal.get(url, headers=user).json()["offers"]["sandbox"]
    submitted = portal.post(
        f"{url}/requests",
        headers=user,
        json={
            "project": "finance",
            "environment": "sandbox",
            "reason": "導入",
            "offer_version": offer["version"],
        },
    )
    assert submitted.status_code == 201
    current = submitted.json()
    assert current["status"] == "pending"
    for actor, reason, status in (
        (leader, "部内確認済み", "pending"),
        (owner, "提供準備完了", "approved"),
    ):
        incoming = portal.get("/api/requests", headers=actor, params={"incoming": True}).json()
        assert any(row["id"] == current["id"] for row in incoming)
        response = portal.post(
            f"/api/requests/{current['id']}",
            headers=actor,
            json={"action": "approve", "revision": current["revision"], "reason": reason},
        )
        assert response.status_code == 200
        current = response.json()
        assert current["status"] == status
    history = portal.get("/api/requests", headers=user).json()
    decisions = next(row for row in history if row["id"] == current["id"])["application"]["decisions"]
    assert [step["reason"] for step in decisions] == ["部内確認済み", "提供準備完了"]


def test_visible_catalog_moves_with_department_membership(portal):
    """限定商品のカタログは子部署の所属を反映し、所属変更後も現在の公開範囲で検索結果を返す。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    for key, parent in (("service", ""), ("local-team", "service")):
        assert (
            portal.put(
                f"/api/workspace/units/{key}",
                headers=admin,
                json={"kind": "department", "name": key, "parent": parent},
            ).status_code
            == 200
        )
    draft = _draft()
    url = _register(portal, owner, draft)
    asset = portal.get(url, headers=owner).json()
    selected = portal.put(
        f"{url}/policy",
        headers=owner,
        params={"revision": asset["revision"]},
        json={"visibility": "restricted", "departments": ["service"]},
    )
    assert selected.status_code == 200
    member = {"subject": subject, "unit_id": "local-team"}
    search = {"q": draft["name"], "environment": "sandbox"}

    def matches():
        result = portal.get("/api/catalog-page", headers=user, params=search)
        assert result.status_code == 200
        page = result.json()
        return page["total"], [item["id"] for item in page["items"]]

    assert matches() == (0, [])
    assert portal.put("/api/workspace/memberships", headers=admin, json=member).status_code == 200
    assert matches() == (1, [asset["id"]])
    assert portal.delete("/api/workspace/memberships", headers=admin, params=member).status_code == 200
    assert matches() == (0, [])


def test_provider_stops_and_reopens_new_applications(portal):
    """提供者が新規受付を停止しても利用権を維持し、再掲載後は別のプロジェクトから新しく申請できる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/units/pilot", headers=admin, json={"kind": "project", "name": "試験"}
        ).status_code
        == 200
    )
    assert (
        portal.put(
            "/api/workspace/memberships", headers=admin, json={"subject": subject, "unit_id": "pilot"}
        ).status_code
        == 200
    )
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": "auto"}}
    url = _register(portal, owner, draft)
    asset = portal.get(url, headers=user).json()
    body = {
        "project": "finance",
        "environment": "sandbox",
        "reason": "日程確認",
        "offer_version": asset["offers"]["sandbox"]["version"],
    }
    initial = portal.post(f"{url}/requests", headers=user, json=body)
    assert initial.status_code == 201 and initial.json()["status"] == "approved"
    status = portal.put(f"{url}/publication", headers=owner, params={"published": False})
    assert status.status_code == 200 and not status.json()["published"]
    rights = portal.get("/api/requests", headers=user, params={"asset_id": asset["id"]}).json()
    assert any(row["id"] == initial.json()["id"] and row["status"] == "approved" for row in rights)
    blocked = portal.post(f"{url}/requests", headers=user, json={**body, "project": "pilot"})
    assert blocked.status_code in (403, 404, 409, 422)
    assert not any(row["project"] == "pilot" for row in portal.get("/api/requests", headers=user).json())
    reopened = publish_asset(portal, f"{url}", owner)
    assert reopened.status_code == 200
    offer = portal.get(url, headers=user).json()["offers"]["sandbox"]
    next_request = portal.post(
        f"{url}/requests",
        headers=user,
        json={**body, "project": "pilot", "offer_version": offer["version"]},
    )
    assert next_request.status_code == 201 and next_request.json()["status"] == "approved"


def test_revision_conflict_does_not_remove_published_product(portal):
    """提供者が商品名を変更した後、古い版番号で削除しても新しい商品と利用者向けの掲載を保持する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    url = _register(portal, owner, draft)
    original = portal.get(url, headers=user).json()
    updated = portal.put(
        url,
        headers=owner,
        params={"revision": original["revision"]},
        json={**draft, "name": "配送営業日照会"},
    )
    assert updated.status_code == 200 and updated.json()["published"]
    stale = portal.delete(url, headers=owner, params={"revision": original["revision"]})
    assert stale.status_code == 409
    actual = portal.get(url, headers=user)
    assert actual.status_code == 200 and actual.json()["name"] == "配送営業日照会"
    removed = portal.delete(url, headers=owner, params={"revision": updated.json()["revision"]})
    assert removed.status_code == 200 and removed.json()["deleted"]
    catalog = portal.get("/api/apis", headers=user, params={"q": "配送営業日照会"}).json()
    assert all(row["id"] != original["id"] for row in catalog)


def test_department_transfer_preserves_visibility_and_auto_approval(portal):
    """限定公開と自動承認に使う部署を移管しても、移管した配下の人は商品を見つけて申請できる。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    for key, parent in (("former", ""), ("combined", ""), ("local", "former")):
        assert (
            portal.put(
                f"/api/workspace/units/{key}",
                headers=admin,
                json={"name": key, "kind": "department", "parent": parent},
            ).status_code
            == 200
        )
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/memberships", headers=admin, json={"subject": subject, "unit_id": "local"}
        ).status_code
        == 200
    )
    url = _register(portal, owner, _draft())
    revision = portal.get(url, headers=owner).json()["revision"]
    policy = {
        "visibility": "restricted",
        "departments": ["former"],
        "auto_departments": ["former"],
        "delegates": ["former"],
    }
    updated = portal.put(f"{url}/policy", headers=owner, params={"revision": revision}, json=policy)
    assert updated.status_code == 200
    moved = portal.post(
        "/api/workspace/units/former/transfer", headers=admin, json={"destination": "combined"}
    )
    assert moved.status_code == 200 and moved.json()["removed"]
    current = portal.get(f"{url}/policy", headers=owner).json()
    assert current["departments"] == current["auto_departments"] == current["delegates"] == ["combined"]
    detail = portal.get(url, headers=user)
    assert detail.status_code == 200
    submitted = portal.post(
        f"{url}/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "集計"},
    )
    assert submitted.status_code == 201 and submitted.json()["status"] == "approved"


def test_overlapping_project_grants_do_not_overwrite_decisions(portal):
    """同じ商品の利用申請が両方のプロジェクトにある場合、移管競合は承認結果や理由を上書きしない。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    owner = headers(portal, "provider")
    url = _register(portal, owner, _draft())
    asset_id = url.rsplit("/", 1)[1]
    subject = portal.get("/api/me", headers=user).json()["subject"]
    snapshots = {}
    for project in ("office-one", "office-two"):
        assert (
            portal.put(
                f"/api/workspace/units/{project}",
                headers=admin,
                json={"name": project, "kind": "project"},
            ).status_code
            == 200
        )
        assert (
            portal.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"subject": subject, "unit_id": project},
            ).status_code
            == 200
        )
        result = portal.post(
            f"{url}/requests",
            headers=user,
            json={"project": project, "environment": "sandbox", "reason": project},
        )
        assert result.status_code == 201
        right = result.json()
        if project == "office-one":
            response = portal.post(
                f"/api/requests/{right['id']}",
                headers=owner,
                json={"action": "approve", "revision": right["revision"], "reason": "受付済み"},
            )
            assert response.status_code == 200
            right = response.json()
        snapshots[project] = (right["id"], right["status"], right["reason"], right["revision"])
    removed = portal.delete(
        "/api/workspace/memberships", headers=admin, params={"subject": subject, "unit_id": "office-two"}
    )
    assert removed.status_code == 200 and removed.json()["removed"]
    moved = portal.post(
        "/api/workspace/units/office-one/transfer", headers=admin, json={"destination": "office-two"}
    )
    assert moved.status_code == 409 and moved.json()["detail"]
    provider_view = portal.get(
        "/api/requests", headers=owner, params={"incoming": True, "asset_id": asset_id}
    ).json()
    assert {
        r["project"]: (r["id"], r["status"], r["reason"], r["revision"]) for r in provider_view
    } == snapshots


def test_existing_api_settings_survive_project_transfer(portal):
    """提供プロジェクトの組織を移管しても既存商品の公開名と提供の責任を後継組織から確認できる。"""
    owner = headers(portal, "provider")
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    url = _register(portal, owner, _draft())
    before = portal.get(url, headers=user).json()
    assert (
        portal.put(
            "/api/workspace/units/successor",
            headers=admin,
            json={"name": "後継提供組織", "kind": "project"},
        ).status_code
        == 200
    )
    moved = portal.post(
        "/api/workspace/units/supply/transfer", headers=admin, json={"destination": "successor"}
    )
    assert moved.status_code == 200, moved.json()
    after = portal.get(url, headers=user)
    assert after.status_code == 200
    item = after.json()
    assert item["owner"] == "successor"
    assert (item["id"], item["slug"], item["published"]) == (before["id"], before["slug"], True)


def test_product_with_unsupported_contract_stays_out_of_catalog(portal):
    """対応対象外のOpenAPI形式を登録しようとしても、公開カタログに不完全な商品は追加されない。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    draft["spec"] = {"swagger": "2.0", "info": {"title": "旧形式", "version": "1"}, "paths": {}}
    invalid = portal.post("/api/apis", headers=owner, json=draft)
    assert invalid.status_code == 422 and invalid.json()["detail"]
    draft["spec"] = _draft()["spec"]
    url = _register(portal, owner, draft)
    search = portal.get("/api/catalog-page", headers=user, params={"q": draft["name"]}).json()
    assert [r["id"] for r in search["items"]] == [url.rsplit("/", 1)[1]]


def test_updated_terms_require_fresh_consent(portal):
    """利用条件の表示後に規約を更新した場合、古い版への同意では申請を受け付けず、新版への同意を保存する。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": "auto", "terms": "初版規約"}}
    url = _register(portal, owner, draft)
    before = portal.get(url, headers=user).json()
    old_version = before["offers"]["sandbox"]["version"]
    draft["offers"]["sandbox"]["terms"] = "改訂した利用規約"
    edited = portal.put(url, headers=owner, params={"revision": before["revision"]}, json=draft)
    assert edited.status_code == 200
    published = publish_asset(portal, f"{url}", owner)
    assert published.status_code == 200
    current = portal.get(url, headers=user).json()["offers"]["sandbox"]
    assert current["version"] != old_version and current["terms"] == "改訂した利用規約"
    submit = {
        "project": "finance",
        "environment": "sandbox",
        "reason": "集計",
        "terms_accepted": True,
        "offer_version": old_version,
    }
    stale = portal.post(f"{url}/requests", headers=user, json=submit)
    assert stale.status_code == 409 and stale.json()["detail"]
    refreshed = portal.post(
        f"{url}/requests", headers=user, json={**submit, "offer_version": current["version"]}
    )
    assert refreshed.status_code == 201
    record = refreshed.json()
    assert record["status"] == "approved" and record["application"]["version"] == current["version"]
    assert record["application"]["terms"] == current["terms"] and record["application"]["terms_accepted"]


def test_personal_workspace_solicits_and_uses_a_single_api(portal):
    """チームに所属していない利用者も個人ワークスペースで申請し、本人用の認証情報で承認された商品を呼べる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "auditor")
    identity = portal.get("/api/me", headers=user).json()
    project, subject = identity["personal_project"], identity["subject"]
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": "auto"}}
    url = _register(portal, owner, draft)
    product = portal.get(url, headers=user).json()
    body = {
        "project": project,
        "environment": "sandbox",
        "personal": True,
        "reason": "本人作業",
        "offer_version": product["offers"]["sandbox"]["version"],
    }
    application = portal.post(f"{url}/requests", headers=user, json=body)
    assert application.status_code == 201
    assert application.json()["status"] == "approved" and application.json()["subject"] == subject
    options = portal.get("/api/credentials/options", headers=user, params={"project": project})
    assert options.status_code == 200
    assert any(item["id"] == product["id"] for item in options.json()["assets"])
    issued = portal.post(
        "/api/credentials",
        headers=user,
        json={
            "mode": "bearer",
            "kind": "personal",
            "project": project,
            "name": "個人専用",
            "api_ids": [product["id"]],
        },
    )
    assert issued.status_code == 201
    credential = issued.json()
    assert credential["project"] == project and credential["kind"] == "personal"
    call = portal.get(
        f"/api/invoke/{product['slug']}/sandbox/{project}/days",
        headers={"Authorization": f"Bearer {credential['access_token']}"},
    )
    assert call.status_code == 200


@pytest.mark.parametrize(
    "role, title, expected_status",
    [
        pytest.param(
            "担当",
            "主任",
            "pending",
            id="manual-review",
            marks=pytest.mark.case_detail("役職が指定条件に一致しなければ提供者の判断を待つ"),
        ),
        pytest.param(
            "主任",
            "主任",
            "approved",
            id="matching-title",
            marks=pytest.mark.case_detail("所属の役職が指定条件に一致すれば自動承認する"),
        ),
    ],
)
def test_title_based_auto_approval(portal, role, title, expected_status):
    """提供者が役職を自動承認条件にすると、申請者の実際の所属上の役職に応じて審査結果が変わる。"""
    admin = headers(portal, "admin")
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    assert (
        portal.put(
            "/api/workspace/units/office",
            headers=admin,
            json={"kind": "department", "name": "業務推進部"},
        ).status_code
        == 200
    )
    assert (
        portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"unit_id": "office", "subject": subject, "title": role},
        ).status_code
        == 200
    )
    url = _register(portal, owner, _draft())
    asset = portal.get(url, headers=owner).json()
    configured = portal.put(
        f"{url}/policy",
        headers=owner,
        params={"revision": asset["revision"]},
        json={"auto_titles": [title]},
    )
    assert configured.status_code == 200 and configured.json()["auto_titles"] == [title]
    requested = portal.post(
        f"{url}/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "担当業務"},
    )
    assert requested.status_code == 201 and requested.json()["status"] == expected_status


def test_personal_approval_as_shared_project_member(portal):
    """プロジェクト内で本人限定の承認を得た人は、チームの承認がなくても本人限定キーで利用できる。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    draft = _draft()
    draft["offers"] = {"sandbox": {"route": "auto"}}
    url = _register(portal, owner, draft)
    asset = portal.get(url, headers=user).json()
    applied = portal.post(
        f"{url}/requests",
        headers=user,
        json={
            "personal": True,
            "project": "finance",
            "environment": "sandbox",
            "reason": "個人作業",
            "offer_version": asset["offers"]["sandbox"]["version"],
        },
    )
    assert applied.status_code == 201 and applied.json()["status"] == "approved"
    issued = portal.post(
        "/api/keys",
        headers=user,
        json={"name": "本人限定", "kind": "personal", "project": "finance", "api_ids": [asset["id"]]},
    )
    assert issued.status_code == 201
    result = portal.get(
        f"/api/invoke/{asset['slug']}/sandbox/finance/days",
        headers={**user, "X-API-Key": issued.json()["secret"]},
    )
    assert result.status_code == 200
