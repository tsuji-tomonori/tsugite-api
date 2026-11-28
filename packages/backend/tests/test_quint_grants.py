"""形式仕様の操作をFastAPIで再生し、応答・保存状態・実際の転送回数を照合する。"""

from unittest.mock import Mock

import pytest
from app.apis import gateway
from starlette.responses import Response

from packages.backend.tests.test_org_access import setup_people
from tests.support.catalog import FORM, headers, invocation_headers, publish_asset
from tests.support.quint import histories


def publish(portal, owner, **overrides):
    asset = portal.post("/api/apis", headers=owner, json={**FORM, **overrides}).raise_for_status().json()
    url = "/api/apis/" + asset["id"]
    publish_asset(portal, url, owner).raise_for_status()
    return asset["id"], url


@pytest.mark.parametrize("states", histories("grants"))
def test_grant_history(states, portal, monkeypatch):
    """利用権の操作列を再生し、取消や別環境では接続先への転送が起きない。"""
    owner, user = headers(portal, "provider"), headers(portal, "consumer")
    asset, url = publish(portal, owner)
    other, _ = publish(portal, owner, slug="other-product")
    call = invocation_headers(portal, user)
    form = {"project": "finance", "environment": "sandbox", "reason": "利用権検証"}
    endpoint = f"/api/requests/{asset}/finance/sandbox"
    path = f"/api/invoke/{asset}/sandbox/finance/items"
    paths = {
        "invoke": path,
        "otherProduct": path.replace(asset, other),
        "otherEnvironment": path.replace("sandbox", "production"),
        "otherProject": path.replace("finance", "supply"),
    }
    upstream = Mock(return_value=Response(status_code=200))
    monkeypatch.setattr(gateway, "dispatch", upstream)
    revision = 1
    for step in states[1:]:
        op = step["operation"]
        before = upstream.call_count
        if op in paths:
            resp = portal.get(paths[op], headers=call)
        elif op == "apply":
            resp = portal.post(url + "/requests", headers=user, json=form)
        elif op == "unpublish":
            resp = portal.put(url + "/publication?published=false", headers=owner)
        else:
            resp = portal.post(
                endpoint,
                headers=user if op == "withdraw" else owner,
                json={"action": op, "revision": revision, "reason": "検証"},
            )
        assert resp.status_code == step["response"], (op, resp.text)
        assert upstream.call_count - before == int(step["forwarded"]), op
        rows = portal.get("/api/requests", headers=user).raise_for_status().json()
        row = next((r for r in rows if r["asset_id"] == asset), None)
        assert (row["status"] if row else "absent") == step["status"]
        if row:
            revision = row["revision"]
        assert portal.get(url, headers=owner).raise_for_status().json()["published"] == step["listed"]


@pytest.mark.parametrize("states", histories("review"))
def test_ordered_history(states, portal, monkeypatch):
    """利用条件と部署・提供者の承認順を再生し、最終判断まで呼び出しを拒否する。"""
    _, people = setup_people(portal, monkeypatch)
    owner = headers(portal, "provider")
    user = people["applicant"]
    offer = {
        "route": "department_provider",
        "terms": "規約",
        "fields": [{"label": "試験ID", "allowed_values": ["QA"]}],
    }
    asset, url = publish(portal, owner, offers={"production": offer})
    version = portal.get(url, headers=user).json()["offers"]["production"]["version"]
    call = invocation_headers(portal, user, "field")
    reviewers = {"department": people["approver"], "provider": owner, "applicant": user}
    row = None
    for step in states[1:]:
        op = step["operation"]
        if op in reviewers:
            assert row is not None, "承認対象の申請が必要です"
            resp = portal.post(
                "/api/requests/" + row["id"],
                headers=reviewers[op],
                json={"action": "approve", "revision": row["revision"], "reason": "確認"},
            )
        elif op == "invoke":
            resp = portal.get(f"/api/invoke/{asset}/production/field/items", headers=call)
        else:
            resp = portal.post(
                url + "/requests",
                headers=user,
                json={
                    "environment": "production",
                    "project": "field",
                    "reason": "切替",
                    "offer_version": "old" if op == "staleTerms" else version,
                    "terms_accepted": op != "noConsent",
                    "answers": {"試験ID": "X" if op == "wrongAnswer" else "QA"},
                },
            )
        assert resp.status_code == step["response"], (op, resp.text)
        rows = portal.get("/api/requests", headers=user).raise_for_status().json()
        row = next((r for r in rows if r["asset_id"] == asset), None)
        assert (row["status"] if row else "absent") == step["status"]
        assert (row.get("stage") or "" if row else "") == step["stage"]


@pytest.mark.parametrize("states", histories("products"))
def test_product_history(states, portal):
    """名称変更では利用権を保持し、構造変更・削除では公開と既存の権利を終了する。"""
    from copy import deepcopy

    from sqlalchemy.orm import Session
    from tsugite_db.models import Access, Asset
    from tsugite_db.session import engine

    owner, user = headers(portal, "provider"), headers(portal, "consumer")
    form = deepcopy(FORM)
    asset = portal.post("/api/apis", headers=owner, json=form).raise_for_status().json()["id"]
    url = "/api/apis/" + asset
    grant_id = f"{asset}/finance/sandbox"
    for step in states:
        op = step["operation"]
        record = portal.get(url, headers=owner).raise_for_status().json()
        params = {"revision": record["revision"]}
        if op == "submitPublication":
            pending = portal.put(url + "/publication?published=true", headers=owner).raise_for_status()
            assert pending.json()["publication_stage"] == "admin"
        elif op == "publish":
            portal.post(
                url + "/publication-decisions",
                headers=headers(portal, "admin"),
                json={"approved": True, "reason": "公開確認", **params},
            ).raise_for_status()
        elif op == "apply":
            grant = (
                portal.post(
                    url + "/requests",
                    headers=user,
                    json={"project": "finance", "environment": "sandbox", "reason": "検証"},
                )
                .raise_for_status()
                .json()
            )
        elif op == "approve":
            portal.post(
                "/api/requests/" + grant_id,
                headers=owner,
                json={"action": "approve", "revision": grant["revision"], "reason": "許可"},
            ).raise_for_status()
        elif op == "delete":
            portal.delete(url, headers=owner, params=params).raise_for_status()
        elif op in ("structure", "rename"):
            if op == "rename":
                form["name"] = "更新後の名称"
            else:
                form["spec"]["info"]["version"] = "2.0"
            portal.put(url, headers=owner, params=params, json=form).raise_for_status()
        with Session(engine()) as db:
            product = db.get_one(Asset, asset)
            right = db.get(Access, grant_id)
            assert (product.published, bool(product.removed_at)) == (step["listed"], step["removed"])
            assert (right.status if right else "absent") == step["status"]


@pytest.mark.parametrize("states", histories("automatic"))
def test_automatic_decisions(states, portal, monkeypatch):
    """所属属性が一致した場合の自動承認と、環境別の自動承認でも必要な規約同意を照合する。"""
    _, people = setup_people(portal, monkeypatch)
    owner = headers(portal, "provider")
    user = people["applicant"]
    for i, step in enumerate(states):
        offer = (
            {"offers": {"sandbox": {"route": "auto", "terms": "規約"}}}
            if step["route"] == "auto"
            else {}
        )
        _, url = publish(portal, owner, slug=f"auto-{i}", **offer)
        revision = portal.get(url, headers=owner).json()["revision"]
        if step["route"] == "legacy":
            portal.put(
                url + "/policy",
                params={"revision": revision},
                headers=owner,
                json={"auto_departments": ["east"] if step["matches"] else []},
            ).raise_for_status()
        revision = portal.get(url, headers=user).json()["revision"]
        result = portal.post(
            url + "/requests",
            headers=user,
            json={
                "reason": "確認",
                "project": "field",
                "environment": "sandbox",
                "offer_version": str(revision),
                "terms_accepted": step["consent"],
            },
        )
        assert result.status_code == step["response"], result.text
        rows = portal.get("/api/requests", headers=user).raise_for_status().json()
        row = next((r for r in rows if r["asset_id"] == url.split("/")[-1]), None)
        assert (row["status"] if row else "absent") == step["status"]


@pytest.mark.parametrize("states", histories("exchange"))
def test_exchange_contract(states, portal):
    """アプリ・システムの交換条件を照合し、失効したシークレットや本人資格の過不足を拒否する。"""
    user, admin = headers(portal, "consumer"), headers(portal, "admin")
    portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": "consumer", "unit_id": "finance", "leader": True},
    ).raise_for_status()
    keys = {}
    for mode in ("app", "system"):
        item = (
            portal.post(
                "/api/credentials",
                headers=user,
                json={
                    "project": "finance",
                    "name": "形式検証",
                    "mode": mode,
                    "kind": "shared" if mode == "system" else "personal",
                },
            )
            .raise_for_status()
            .json()
        )
        updated = (
            portal.post(f"/api/credentials/{item['id']}/rotate", headers=user).raise_for_status().json()
        )
        keys[mode] = item["client_id"], item["client_secret"], updated["client_secret"]
    for step in states:
        client, old, current = keys[step["mode"]]
        resp = portal.post(
            "/api/auth/token",
            headers=user if step["identity"] else {},
            json={"client_id": client, "client_secret": current if step["secretValid"] else old},
        )
        assert resp.status_code == step["response"], resp.text
        assert ("access_token" in resp.json()) == (step["response"] == 200)
