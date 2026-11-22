from copy import deepcopy

from app.apis.gateway import allowed_path, operation_template
from pytest_given import given, scenario, then, when

from tests.support.catalog import FORM, SPEC, headers


@scenario("公開から取消まで、環境ごとの利用権限と監査を追跡する", tags=["CAT", "AUTH", "AUDIT"])
def test_lifecycle(portal):
    """承認した環境だけで呼び出せ、取消後の拒否を監査できる"""
    api = portal
    with given("提供・利用・監査の3人がログインする"):
        p = headers(api, "provider")
        u = headers(api, "consumer")
        audit = headers(api, "auditor")
        assert api.get("/api/apis").status_code == 401
        assert api.post("/api/apis", headers=u, json=FORM).status_code == 403
        created = api.post("/api/apis", headers=p, json=FORM)
        assert created.status_code == 201, created.text
        key = created.json()["id"]
        url = "/api/apis/" + key
        path = f"/api/invoke/{key}/sandbox/finance/items"
        assert api.get(url, headers=u).status_code == 404
        assert api.get("/api/apis?inventory=true", headers=p).json()[0]["id"] == key
    with when("APIを公開し、利用チームが検証環境へのアクセスを申請する"):
        assert api.put(url + "/publication?published=true", headers=u).status_code == 403
        assert api.put(url + "/publication?published=true", headers=p).status_code == 200
        assert len(api.get("/api/apis?q=棚卸", headers=u).json()) == 1
        apply = {"project": "finance", "environment": "sandbox", "reason": "月次の在庫確認"}
        assert (
            api.post(url + "/requests", headers=u, json={**apply, "project": "supply"}).status_code
            == 403
        )
        res = api.post(url + "/requests", headers=u, json=apply)
        assert res.status_code == 201, res.text
        assert api.post(url + "/requests", headers=u, json=apply).status_code == 409
        endpoint = "/api/requests/" + res.json()["id"]
        approval = {"action": "approve", "revision": res.json()["revision"], "reason": "用途を確認"}
        assert api.get(path, headers=u).status_code == 403
        assert api.post(endpoint, headers=u, json=approval).status_code == 403
        active = api.post(endpoint, headers=p, json=approval)
        assert active.status_code == 200
    with then("承認した環境だけ呼べ、掲載の取り下げ後も既存の利用者は使える"):
        assert api.post(endpoint, headers=p, json=approval).status_code == 409
        assert api.get(path, headers=u).json()["project"] == "finance"
        assert api.get(path.replace("sandbox", "production"), headers=u).status_code == 403
        assert api.post(path, headers=u).status_code == 404
        assert api.get(path + "/unknown", headers=u).status_code == 404
        assert api.put(url + "/publication?published=false", headers=p).status_code == 200
        assert api.get("/api/apis", headers=u).json() == []
        assert api.get(url, headers=u).status_code == 200
        assert api.get(path, headers=u).status_code == 200
        assert (
            api.post(
                url + "/requests", headers=u, json={**apply, "environment": "production"}
            ).status_code
            == 409
        )
    with when("提供チームが利用権限を取り消す"):
        revoke = {"action": "revoke", "revision": active.json()["revision"], "reason": "棚卸し終了"}
        assert api.post(endpoint, headers=p, json=revoke).status_code == 200
        denied = api.get(path, headers=u)
    with then("同じトークンの再利用を拒否し、申請から実行結果まで追跡できる"):
        assert denied.status_code == 403
        assert api.get(url, headers=u).status_code == 404
        events = api.get("/api/audit", headers=audit).json()
        assert {
            "register",
            "publish",
            "unpublish",
            "apply",
            "approve",
            "revoke",
            "invoke.start",
            "invoke.end",
            "invoke.denied",
        } <= {e["action"] for e in events}
        filtered = api.get(
            "/api/audit", params={"request_id": denied.headers["x-request-id"]}, headers=audit
        ).json()
        assert len(filtered) == 1 and filtered[0]["actor"] == "consumer"
        assert api.get("/api/requests?incoming=true", headers=u).json() == []
        assert api.get("/api/requests", headers=audit).json() == []


@scenario("却下と申請取り下げの後に再申請できる", tags=["AUTH"])
def test_reapply(portal):
    """却下後に再申請でき、古い判断の再適用を拒否する"""
    with given("公開済みのAPIがある"):
        p = headers(portal, "provider")
        u = headers(portal, "consumer")
        key = portal.post("/api/apis", headers=p, json=FORM).json()["id"]
        url = f"/api/apis/{key}"
        portal.put(url + "/publication?published=true", headers=p)
    with when("利用者が申請し、提供者が却下する"):
        form = {"project": "finance", "environment": "sandbox", "reason": "検証"}
        row = portal.post(url + "/requests", json=form, headers=u).json()
        path = "/api/requests/" + row["id"]
        res = portal.post(
            path,
            json={"action": "reject", "reason": "用途の追記", "revision": row["revision"]},
            headers=p,
        )
    with then("再申請と取下げができ、古い判断は再適用できない"):
        assert res.json()["status"] == "rejected"
        second = portal.post(url + "/requests", json=form, headers=u)
        assert second.status_code == 201
        old = portal.post(
            path, json={"action": "approve", "reason": "再確認", "revision": row["revision"]}, headers=p
        )
        assert old.status_code == 409
        assert (
            portal.post(
                path,
                json={"action": "withdraw", "reason": "検証終了", "revision": second.json()["revision"]},
                headers=u,
            ).json()["status"]
            == "withdrawn"
        )


def test_registration_validation(portal):
    """外部参照、環境違いの接続先、不正な仕様の登録を拒否する"""
    owner = headers(portal, "provider")
    spec = deepcopy(SPEC)
    spec["paths"]["/items"]["get"] = {"$ref": "https://example.invalid/operation"}
    assert portal.post("/api/apis", headers=owner, json={**FORM, "spec": spec}).status_code == 422
    assert (
        portal.post(
            "/api/apis", headers=owner, json={**FORM, "targets": {"sandbox": "sample-production"}}
        ).status_code
        == 422
    )
    assert (
        portal.post("/api/apis", headers=owner, json={**FORM, "spec": {"paths": {}}}).status_code == 422
    )


def test_route_contract():
    """OpenAPIの固定パスを優先し、許可された操作だけを通す"""
    spec = {"paths": {"/notes/{id}": {"get": {}}, "/notes/admin": {"post": {}}}}
    assert operation_template(spec, "GET", "/notes/123") == "/notes/{id}"
    assert allowed_path(spec, "GET", "/notes/123")
    assert not allowed_path(spec, "GET", "/notes/admin")
    assert not allowed_path(spec, "GET", "/notes/..")


def test_demo_disabled_on_lambda(monkeypatch):
    """Lambdaではデモ用ログインを無効にする"""
    from app.core.config import local_demo
    from app.main import create_app

    monkeypatch.setenv("TSUGITE_DEMO", "1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test")
    assert not local_demo()
    assert not any(
        getattr(route, "path", None) == "/api/demo/{persona}" for route in create_app().routes
    )


def test_withdrawal_and_audit_visibility(portal, monkeypatch):
    """未申請・取下げ後の権限を拒否し、他プロジェクトに監査記録を開示しない"""
    from app.core.auth import DEMO_GROUPS

    monkeypatch.setitem(DEMO_GROUPS, "other", ["use-procurement"])
    owner, user, other, auditor = (
        headers(portal, who) for who in ("provider", "consumer", "other", "auditor")
    )
    created = portal.post("/api/apis", headers=owner, json=FORM).json()
    asset = created["id"]
    url = f"/api/apis/{asset}"
    portal.put(url + "/publication?published=true", headers=owner).raise_for_status()
    path = f"/api/invoke/{asset}/sandbox/finance/items"
    assert portal.get(path, headers=user).status_code == 403
    right = portal.post(
        url + "/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "検証"},
    ).json()
    decision = {"action": "withdraw", "revision": right["revision"], "reason": "依頼中止"}
    assert portal.post("/api/requests/" + right["id"], headers=other, json=decision).status_code == 403
    portal.post("/api/requests/" + right["id"], headers=user, json=decision).raise_for_status()
    denied = portal.get(path, headers=user)
    assert denied.status_code == 403
    trace = {"request_id": denied.headers["x-request-id"], "action": "invoke.denied"}
    for allowed in (owner, user, auditor):
        assert [e["detail"] for e in portal.get("/api/audit", params=trace, headers=allowed).json()] == [
            "403"
        ]
    assert portal.get("/api/audit", params=trace, headers=other).json() == []
    assert portal.get("/api/requests", headers=other, params={"asset_id": asset}).json() == []
    assert portal.get("/api/requests", headers=user).json()[0]["decision_reason"] == "依頼中止"
