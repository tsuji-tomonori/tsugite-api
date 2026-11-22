"""Exercise issued keys across the HTTP boundary with Cognito and a TLS upstream."""

import json
import os
import secrets

import httpx
import jwt

from tests.e2e.aws.https_stock import https_stock
from tests.e2e.aws.test_portal import live_portal
from tools.seed_marketplace import CATALOG, offer


def another_finance_user(aws, first_token):
    # The live portal verifies this independently issued access token via JWKS.
    identity = jwt.decode(first_token, options={"verify_signature": False})
    idp = aws.client("cognito-idp")
    pool = identity["iss"].split("/")[-1]
    name = "another-finance-reader"
    password = secrets.token_urlsafe(24) + "9aA!"
    idp.admin_create_user(UserPoolId=pool, Username=name, MessageAction="SUPPRESS")
    idp.admin_set_user_password(UserPoolId=pool, Username=name, Password=password, Permanent=True)
    idp.admin_add_user_to_group(UserPoolId=pool, Username=name, GroupName="use-finance")
    return idp.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=identity["client_id"],
        AuthParameters={"USERNAME": name, "PASSWORD": password},
    )["AuthenticationResult"]["AccessToken"]


def subscribe(api, product, provider, consumer):
    asset = (
        api.post("apis", headers=provider, json={**offer(product), "base_path": "/v1"})
        .raise_for_status()
        .json()["id"]
    )
    api.put(f"apis/{asset}/publication", params={"published": True}, headers=provider).raise_for_status()
    grant = (
        api.post(
            f"apis/{asset}/requests",
            headers=consumer,
            json={
                "project": "finance",
                "environment": product["environment"],
                "reason": "棚卸用の業務処理",
            },
        )
        .raise_for_status()
        .json()
    )
    api.post(
        "requests/" + grant["id"],
        headers=provider,
        json={"action": "approve", "reason": "利用部門を確認", "revision": grant["revision"]},
    ).raise_for_status()
    return asset, f"invoke/{asset}/{product['environment']}/finance{product['path']}"


def test_scoped_keys_reach_https(aws, resources, tmp_path, request):
    with (
        https_stock(aws, tmp_path, os.environ["AWS_CA_BUNDLE"]) as (binding, ca, calls),
        live_portal(aws, resources, tmp_path, "scoped-api-keys", binding, ca) as (url, tokens),
        httpx.Client(base_url=url + "/api/", trust_env=False) as api,
    ):
        provider = {"Authorization": "Bearer " + tokens["owner"]}
        consumer = {"Authorization": "Bearer " + tokens["user"]}
        peer = {"Authorization": "Bearer " + another_finance_user(aws, tokens["user"])}
        subject = api.get("me", headers=consumer).raise_for_status().json()["subject"]
        peer_identity = api.get("me", headers=peer).raise_for_status().json()
        assert peer_identity["projects"] == ["finance"] and peer_identity["subject"] != subject

        stock, read_stock = subscribe(api, CATALOG[0], provider, consumer)
        _, read_rates = subscribe(api, CATALOG[2], provider, consumer)
        issued = {}
        for kind in ("shared", "personal"):
            issued[kind] = (
                api.post(
                    "keys",
                    headers=consumer,
                    json={
                        "project": "finance",
                        "kind": kind,
                        "name": "棚卸 " + kind,
                        "api_ids": [stock],
                    },
                )
                .raise_for_status()
                .json()
            )
        shared = {"Authorization": "Bearer " + issued["shared"]["secret"]}
        personal = {**consumer, "X-API-Key": issued["personal"]["secret"]}

        for kind, auth in (("shared", shared), ("personal", personal)):
            success = api.get(read_stock, headers=auth)
            assert success.raise_for_status().json() == {"items": [{"sku": "TS-01", "stock": 12}]}
            trace = success.headers["x-request-id"]
            journal = (
                api.get("audit", headers=provider, params={"request_id": trace})
                .raise_for_status()
                .json()
            )
            assert {e["action"] for e in journal} == {"invoke.start", "invoke.end"}
            logs = (
                api.get("access-logs", headers=provider, params={"request_id": trace})
                .raise_for_status()
                .json()
            )
            assert len(logs) == 1
            log = logs[0]
            assert (
                log["key_id"],
                log["request_id"],
                log["method"],
                log["operation"],
                log["status"],
            ) == (issued[kind]["id"], trace, "GET", "/items", 200)
            sample = json.dumps(
                {"業務監査": journal[::-1], "HTTPアクセスログ": log}, ensure_ascii=False, indent=2
            )
            assert all(key["secret"] not in sample for key in issued.values())
            request.node.user_properties.append(("trace_sample", sample))
            assert api.get(read_rates, headers=auth).status_code == 403

        stolen = api.get(read_stock, headers={**peer, "X-API-Key": issued["personal"]["secret"]})
        assert stolen.status_code in {401, 403}
        for kind, auth in (("shared", shared), ("personal", personal)):
            api.delete("keys/" + issued[kind]["id"], headers=consumer).raise_for_status()
            assert api.get(read_stock, headers=auth).status_code in {401, 403}
        upstream = [(method, path) for method, path in calls if method != "HEAD"]
        assert upstream == [("GET", "/warehouse/v1/items")] * 2
        request.node.user_properties.append(
            (
                "finding",
                "EmulatorのCognitoで同一プロジェクトの2人を認証。共有キーと本人キーは在庫照会を各1回実行し、TLS接続先がSKU TS-01・在庫12を返した。"
                f"スコープ外の為替照会2回、別人による本人キーの使用（HTTP {stolen.status_code}）、失効後2回の業務転送は0件。成功2件のキーIDをアクセスログで照合。",
            )
        )
