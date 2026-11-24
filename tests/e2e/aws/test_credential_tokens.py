"""Real Cognito identities, scoped token exchange and TLS business calls."""

import json
import os

import httpx

from tests.e2e.aws.https_stock import https_stock
from tests.e2e.aws.test_portal import live_portal
from tests.e2e.aws.test_scoped_keys import another_finance_user, subscribe
from tools.demo.seed_marketplace import CATALOG, offer


def stock_and_orders(api, provider, consumer):
    listing = offer(CATALOG[0])
    listing["base_path"] = "/v1"
    orders = offer(CATALOG[4])["spec"]
    listing["spec"]["paths"]["/orders"] = orders["paths"]["/orders"]
    listing["spec"]["components"]["schemas"].update(orders["components"]["schemas"])
    asset = api.post("apis", headers=provider, json=listing).raise_for_status().json()["id"]
    api.put(f"apis/{asset}/publication?published=true", headers=provider).raise_for_status()
    grant = (
        api.post(
            f"apis/{asset}/requests",
            headers=consumer,
            json={"project": "finance", "environment": "production", "reason": "在庫と発注の契約確認"},
        )
        .raise_for_status()
        .json()
    )
    api.post(
        "requests/" + grant["id"],
        headers=provider,
        json={"action": "approve", "reason": "契約を確認", "revision": grant["revision"]},
    ).raise_for_status()
    return asset, f"invoke/{asset}/production/finance"


def test_client_tokens_reach_https(aws, resources, tmp_path, request):
    """AWS EmulatorのCognito利用者とシステムのトークンを発行し、HTTPS到達・拒否・秘密更新を確認する"""
    with (
        https_stock(aws, tmp_path, os.environ["AWS_CA_BUNDLE"]) as (binding, ca, calls),
        live_portal(aws, resources, tmp_path, "client-token-exchange", binding, ca) as (url, tokens),
        httpx.Client(base_url=url + "/api/", trust_env=False) as api,
    ):
        owner = {"Authorization": "Bearer " + tokens["owner"]}
        user = {"Authorization": "Bearer " + tokens["user"]}
        peer = {"Authorization": "Bearer " + another_finance_user(aws, tokens["user"])}
        subject = api.get("me", headers=user).raise_for_status().json()["subject"]
        api.put(
            "workspace/memberships",
            headers={"Authorization": "Bearer " + tokens["administrator"]},
            json={"subject": subject, "unit_id": "finance", "title": "棚卸担当", "leader": True},
        ).raise_for_status()
        asset, base = stock_and_orders(api, owner, user)
        _, rates = subscribe(api, CATALOG[2], owner, user)
        credentials = {}
        credential_ids = {}
        issued_tokens = {}
        proofs = []
        for mode in ("app", "system"):
            credential = (
                api.post(
                    "credentials",
                    headers=user,
                    json={
                        "project": "finance",
                        "kind": "shared",
                        "mode": mode,
                        "name": "在庫読取 " + mode,
                        "ttl_minutes": 60,
                        "refresh_minutes": 30,
                        "api_ids": [asset],
                        "operations": {asset: ["GET /items"]},
                        "users": [subject] if mode == "app" else [],
                    },
                )
                .raise_for_status()
                .json()
            )
            creds = {"client_id": credential["client_id"], "client_secret": credential["client_secret"]}
            credentials[mode] = creds
            credential_ids[mode] = credential["id"]
            headers = user if mode == "app" else {}
            if mode == "app":
                for other_identity in ({}, peer):
                    assert api.post("auth/token", headers=other_identity, json=creds).status_code in {
                        401,
                        403,
                    }
            result = api.post("auth/token", headers=headers, json=creds).raise_for_status()
            token = result.json()
            assert token["token_type"].lower() == "bearer" and 0 < token["expires_in"] <= 3600
            assert 0 <= token["refresh_after"] <= token["expires_in"]
            assert "no-store" in result.headers["cache-control"]
            denied = api.get(
                base + "/items", headers={"Authorization": "Bearer " + creds["client_secret"]}
            )
            assert denied.status_code in {401, 403}
            auth = {"Authorization": "Bearer " + token["access_token"]}
            issued_tokens[mode] = auth
            success = api.get(base + "/items", headers=auth).raise_for_status()
            assert success.json() == {"items": [{"sku": "TS-01", "stock": 12}]}
            request_id = success.headers["x-request-id"]
            log = (
                api.get("access-logs", params={"scope": "audit", "request_id": request_id}, headers=user)
                .raise_for_status()
                .json()
            )
            events = (
                api.get("audit", params={"request_id": request_id}, headers=user)
                .raise_for_status()
                .json()
            )
            assert len(log) == 1 and log[0]["key_id"] == credential["id"]
            if mode == "app":
                assert log[0]["actor"] == subject
            else:
                assert log[0]["actor"] != subject
            assert {e["action"] for e in events} == {"invoke.start", "invoke.end"}
            proofs.append(
                json.dumps(
                    {"業務監査": events[::-1], "HTTPアクセスログ": log[0]}, ensure_ascii=False, indent=2
                )
            )
            # Both calls are contract-approved and the TLS upstream handles both;
            # only the new client's invocation scope must prevent forwarding.
            assert api.post(base + "/orders", headers=auth, json={"units": 3}).status_code == 403
            assert api.get(rates, headers=auth).status_code == 403

        # A short-lived delegated token must observe a provider's later user restriction.
        api.put(
            f"apis/{asset}/operation-policy",
            headers=owner,
            json={"subject": subject, "operations": []},
        ).raise_for_status()
        assert api.get(base + "/items", headers=issued_tokens["app"]).status_code == 403
        client = credentials["system"]
        renewed = api.post("auth/token", json=client).raise_for_status().json()["access_token"]
        token_changed = "Bearer " + renewed != issued_tokens["system"]["Authorization"]
        assert token_changed
        new_auth = {"Authorization": "Bearer " + renewed}
        assert (
            api.get(base + "/items", headers=new_auth).raise_for_status().json()["items"][0]["stock"]
            == 12
        )
        rotated = (
            api.post("credentials/" + credential_ids["system"] + "/rotate", headers=user)
            .raise_for_status()
            .json()
        )
        secret_changed = rotated["client_secret"] != client["client_secret"]
        assert secret_changed
        assert api.post("auth/token", json=client).status_code in {401, 403}
        for old in (issued_tokens["system"], new_auth):
            assert api.get(base + "/items", headers=old).status_code in {401, 403}
        replacement_secret = {**client, "client_secret": rotated["client_secret"]}
        active = (
            api.post("auth/token", json=replacement_secret).raise_for_status().json()["access_token"]
        )
        assert api.get(base + "/items", headers={"Authorization": "Bearer " + active}).is_success
        assert [(m, p) for m, p in calls if m != "HEAD"] == [("GET", "/warehouse/v1/items")] * 4
        for sample in proofs:
            assert not any(
                material["client_secret"] in sample
                for material in (*credentials.values(), replacement_secret)
            )
            assert not any(
                authorization["Authorization"].split(" ", 1)[1] in sample
                for authorization in issued_tokens.values()
            )
            request.node.user_properties.append(("trace_sample", sample))
        request.node.user_properties.append(
            (
                "finding",
                "AWS EmulatorのCognito本人を確認してアプリの短期Bearerを交換。人を持たないシステムの交換・再発行・秘密値更新も確認。TLS接続先の在庫照会は合計4回で、権限外の発注・為替照会、本人の操作権限を停止した後のアプリ呼び出し・旧世代のトークンによる追加転送は0件。",
            )
        )
