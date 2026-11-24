# Cognitoで識別した2人が画面で承認し、在庫照会・取消・監査まで進める。
import json
import os
import secrets
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_given import scenario

from tests.e2e.aws.https_stock import https_stock
from tests.e2e.aws.stock_functions import STOCK_FUNCTIONS
from tests.support.catalog import invocation_headers
from tests.support.catalog_journey import catalog_journey
from tests.support.portal_server import ROOT, serve_portal


def http_access_records(path):
    lines = path.read_text().splitlines()
    records = (json.loads(line) for line in lines if line.lstrip().startswith("{"))
    return [record for record in records if record.get("event") == "http.access"]


@contextmanager
def cognito_users(aws):
    cognito = aws.client("cognito-idp")
    pool = cognito.create_user_pool(PoolName="tsugite-password-test")["UserPool"]["Id"]
    client = cognito.create_user_pool_client(
        UserPoolId=pool,
        ClientName="test-portal",
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )["UserPoolClient"]["ClientId"]
    tokens = {}
    for name, group in [("owner", "own-supply"), ("user", "use-finance"), ("administrator", "admin")]:
        password = secrets.token_urlsafe(24) + "9aA!"
        cognito.create_group(UserPoolId=pool, GroupName=group)
        cognito.admin_create_user(UserPoolId=pool, Username=name, MessageAction="SUPPRESS")
        cognito.admin_set_user_password(
            UserPoolId=pool, Username=name, Password=password, Permanent=True
        )
        cognito.admin_add_user_to_group(UserPoolId=pool, Username=name, GroupName=group)
        result = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=client,
            AuthParameters={"USERNAME": name, "PASSWORD": password},
        )
        tokens[name] = result["AuthenticationResult"]["AccessToken"]
    yield (
        {
            "issuer": os.environ["AWS_ENDPOINT_URL"] + "/" + pool,
            "portal_client": client,
            "pool_id": pool,
            "projects": ["finance", "supply"],
        },
        tokens,
    )


@contextmanager
def machine_tokens(folder):
    # Hosted OAuth token issuance is unavailable on this emulator version.
    # Exercise the deployed application's JWT verification and grants over HTTP.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    discovery = folder / ".well-known"
    discovery.mkdir()
    (discovery / "jwks.json").write_text(
        json.dumps({"keys": [{**jwk, "kid": "e2e", "alg": "RS256", "use": "sig"}]})
    )
    with ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=folder)
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        issuer = f"http://127.0.0.1:{server.server_port}"

        def token(subject, client, groups, scope):
            claims = {
                "sub": subject,
                "iss": issuer,
                "exp": int(time()) + 300,
                "client_id": client,
                "token_use": "access",
                "cognito:groups": groups,
                "scope": scope,
            }
            return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "e2e"})

        try:
            yield (
                {
                    "issuer": issuer,
                    "portal_client": "portal",
                    "machine_projects": [{"client": "batch", "project": "finance"}],
                },
                {
                    "owner": token("owner", "portal", ["own-supply"], "openid"),
                    "user": token("user", "portal", ["use-finance"], "openid"),
                    "administrator": token("administrator", "portal", ["admin"], "openid"),
                    "machine": token("batch", "batch", [], "hub/invoke"),
                    "no_scope": token("batch", "batch", [], "openid"),
                },
            )
        finally:
            server.shutdown()
            thread.join()


@contextmanager
def live_portal(aws, resources, tmp_path, identity, binding=None, ca=None):
    auth = cognito_users(aws) if identity != "machine" else machine_tokens(tmp_path)
    with auth as (config, tokens):
        config["targets"] = {
            "sample-" + env: {
                **(binding or {"kind": "lambda", "address": resources["transport-" + env]}),
                "owner": "supply",
                "environment": env,
            }
            for env in STOCK_FUNCTIONS
        }
        param = "/tsugite/" + tmp_path.name
        aws.client("ssm").put_parameter(Name=param, Type="String", Value=json.dumps(config))
        env = {
            **os.environ,
            "TSUGITE_DEMO": "0",
            "SSL_CERT_FILE": str(ca or os.environ["AWS_CA_BUNDLE"]),
            "HUB_SETTINGS_PARAMETER": param,
            "SPEC_BUCKET": next(
                v for k, v in resources.items() if k.startswith("RuntimeSpecifications")
            ),
            "DATABASE_URL": "sqlite:///" + str(tmp_path / "catalog.db"),
        }
        with (tmp_path / "access.log").open("w") as log, serve_portal(env, log=log) as url:
            yield url, tokens


@scenario(
    "Cognitoで識別した2人が画面から申請し、承認済みの在庫照会Lambdaを呼ぶ", tags=["CAT", "AUTH", "AUDIT"]
)
def test_cognito_browser(aws, resources, tmp_path, request):
    """Cognitoで識別した2人が画面で承認し、在庫照会・取消・監査まで進める"""
    with live_portal(aws, resources, tmp_path, "cognito-browser") as (url, tokens):
        response = httpx.get(
            url + "/api/me", headers={"Authorization": "Bearer " + tokens["user"]}, trust_env=False
        )
        response.raise_for_status()
        catalog_journey(url, request.node, tokens, response.json()["subject"])


@pytest.mark.parametrize(
    ("identity", "upstream", "environment"),
    [
        pytest.param(
            "cognito",
            "lambda",
            "staging",
            marks=pytest.mark.case_detail("検証環境の在庫を照会する"),
        ),
        pytest.param(
            "cognito",
            "lambda",
            "production",
            marks=pytest.mark.case_detail("本番環境の在庫を照会する"),
        ),
        pytest.param(
            "cognito",
            "lambda",
            "sandbox",
            id="cognito-lambda",
            marks=pytest.mark.case_detail("利用者がLambdaへ接続する"),
        ),
        pytest.param(
            "machine",
            "lambda",
            "sandbox",
            id="machine-lambda",
            marks=pytest.mark.case_detail("システムがLambdaへ接続する"),
        ),
        pytest.param(
            "cognito",
            "https",
            "sandbox",
            id="cognito-https",
            marks=pytest.mark.case_detail("利用者がHTTPS先へ接続する"),
        ),
    ],
)
def test_approved_calls_reach_upstream(
    aws, resources, tmp_path, identity, upstream, environment, request
):
    """承認した呼び出しを接続先へ転送し、権限取消後は遮断する"""
    service = (
        https_stock(aws, tmp_path, os.environ["AWS_CA_BUNDLE"])
        if upstream == "https"
        else nullcontext((None, None, None))
    )
    with (
        service as (binding, ca, calls),
        live_portal(aws, resources, tmp_path, identity, binding, ca) as (url, tokens),
        httpx.Client(base_url=url + "/api/", trust_env=False) as api,
    ):

        def headers(who):
            return {"Authorization": "Bearer " + tokens[who]}

        owner, user = headers("owner"), headers("user")
        invoker = headers("machine") if identity == "machine" else user
        result = api.get("me", headers=user)
        assert result.status_code == 200, result.text
        user_id = result.json()["subject"]
        assert result.json()["projects"] == ["finance"]
        if identity == "machine":
            assert api.get("me", headers=invoker).status_code == 403
            assert api.get("me", headers=headers("no_scope")).status_code == 401
        data = {
            "name": "在庫",
            "slug": "stock-lookup",
            "summary": "棚卸し",
            "owner": "supply",
            "targets": {env: "sample-" + env for env in STOCK_FUNCTIONS},
            "spec": json.loads((ROOT / "docs/examples/stock.openapi.json").read_text()),
        }
        if binding:
            data["base_path"] = "/v1"
        result = api.post("apis", headers=owner, json=data)
        assert result.status_code == 201, result.text
        key = result.json()["id"]
        asset = "apis/" + key
        result = api.put(asset + "/publication?published=true", headers=owner)
        assert result.status_code == 200, result.text
        form = {"project": "finance", "environment": environment, "reason": "棚卸し"}
        result = api.post(asset + "/requests", headers=user, json=form)
        assert result.status_code == 201, result.text
        right = result.json()
        if identity != "machine":
            invoker = invocation_headers(api, user, endpoint="credentials")
        path = f"invoke/{key}/{environment}/finance/items"
        assert api.get(path, headers=invoker).status_code == 403
        decide = "requests/" + right["id"]
        rejection = {"action": "reject", "reason": "倉庫の指定が必要", "revision": right["revision"]}
        api.post(decide, headers=owner, json=rejection).raise_for_status()
        rejected = api.get(path, headers=invoker)
        assert rejected.status_code == 403
        denied_id = rejected.headers["x-request-id"]
        denied = api.get(
            "audit", headers=headers("administrator"), params={"request_id": denied_id}
        ).json()
        assert [(e["action"], e["detail"]) for e in denied] == [("invoke.denied", "403")]
        if calls is not None:
            assert all(method == "HEAD" for method, _ in calls)
        form["reason"] = "岐阜倉庫の棚卸し"
        right = api.post(asset + "/requests", headers=user, json=form).raise_for_status().json()
        approval = {"action": "approve", "reason": "用途を確認", "revision": right["revision"]}
        assert api.post(decide, headers=user, json=approval).status_code == 403
        result = api.post(decide, headers=owner, json=approval)
        assert result.status_code == 200, result.text
        approved = result.json()
        assert api.get(path.replace("/finance/", "/supply/"), headers=invoker).status_code == 403
        other = "sandbox" if environment == "production" else "production"
        assert api.get(f"invoke/{key}/{other}/finance/items", headers=invoker).status_code == 403
        call = api.get(path, headers=invoker)
        assert call.status_code == 200, call.text
        assert call.json() == {"items": [{"sku": "TS-01", "stock": 12}]}
        if upstream == "lambda":
            assert api.get(path + "/TS-01", headers=invoker).raise_for_status().json() == {
                "sku": "TS-01",
                "stock": 12,
            }
            missing = api.get(path + "/UNKNOWN", headers=invoker)
            assert missing.status_code == 404
            assert missing.json() == {"message": "商品が見つかりません"}
        audit = api.get(
            "audit",
            headers=headers("administrator"),
            params={"request_id": call.headers["x-request-id"]},
        ).json()
        assert {e["action"] for e in audit} == {"invoke.start", "invoke.end"}
        for e in audit:
            assert (e["actor"], e["asset_id"], e["environment"], e["project"]) == (
                "batch" if identity == "machine" else user_id,
                key,
                environment,
                "finance",
            )
            assert datetime.fromisoformat(e["at"])
        revoke = {"action": "revoke", "reason": "終了", "revision": approved["revision"]}
        assert api.post(decide, headers=owner, json=revoke).status_code == 200
        assert api.get(path, headers=invoker).status_code == 403
        log_rows = http_access_records(tmp_path / "access.log")
        for response in (rejected, call):
            matches = [row for row in log_rows if row["request_id"] == response.headers["x-request-id"]]
            assert len(matches) == 1
            assert (matches[0]["status"], matches[0]["method"]) == (response.status_code, "GET")
            assert datetime.fromisoformat(matches[0]["at"]).tzinfo
            assert matches[0]["operation"] == ("/items" if response.is_success else None)
            assert matches[0]["level"] == ("INFO" if response.is_success else "WARN")
            assert matches[0]["source"] == "api"
            assert set(matches[0]) == {
                "event",
                "at",
                "route",
                "operation",
                "method",
                "request_id",
                "status",
                "source",
                "level",
                "reason",
                "screen",
                "actor_id",
                "target_subject_id",
                "asset_id",
                "operator_action",
            }
            if upstream == "https":
                request.node.user_properties.append(
                    (
                        "trace_sample",
                        json.dumps(
                            {
                                "業務監査": denied if response.status_code == 403 else audit[::-1],
                                "HTTPアクセスログ": matches[0],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                )
        request.node.user_properties.append(
            (
                "finding",
                f"却下後 GET 403 → invoke.denied（{denied_id}）。再申請・承認後 GET 200 → invoke.start / invoke.end（{call.headers['x-request-id']}）。両IDをHTTPアクセスログの同一ステータスと照合。",
            )
        )
        if calls is not None:
            assert ("HEAD", "/warehouse") in calls
            assert [path for method, path in calls if method == "GET"] == ["/warehouse/v1/items"]


def test_marketplace_contracts(aws, resources, tmp_path, request):
    """6種類を個別に登録・公開・承認して実行し、HTTPSの受信・業務応答・監査記録を照合する"""
    from packages.tools.demo.seed_marketplace import CATALOG, offer

    expected = [
        {"items": [{"sku": "TS-01", "stock": 12}]},
        {"parcel": "JP17", "status": "配送中"},
        {"currency": "JPY", "rate": 1},
        {"stores": ["岐阜", "名古屋"]},
        {"order": "PO-17", "units": 3},
        {"business_date": "2026-11-24"},
    ]
    with (
        https_stock(aws, tmp_path, os.environ["AWS_CA_BUNDLE"]) as (binding, ca, calls),
        live_portal(aws, resources, tmp_path, "catalog-six", binding, ca) as (url, tokens),
        httpx.Client(base_url=url + "/api/", trust_env=False) as api,
    ):
        owner, user = ({"Authorization": "Bearer " + tokens[k]} for k in ("owner", "user"))
        call_headers = invocation_headers(api, user, endpoint="credentials")
        for product, answer in zip(CATALOG[:6], expected, strict=True):
            data = {**offer(product), "base_path": "/v1"}
            asset = api.post("apis", headers=owner, json=data).raise_for_status().json()["id"]
            api.put(
                f"apis/{asset}/publication", params={"published": True}, headers=owner
            ).raise_for_status()
            env = product["environment"]
            form = {"project": "finance", "environment": env, "reason": "月次集計"}
            right = api.post(f"apis/{asset}/requests", headers=user, json=form).raise_for_status().json()
            api.post(
                "requests/" + right["id"],
                headers=owner,
                json={"action": "approve", "reason": "利用目的を確認", "revision": right["revision"]},
            ).raise_for_status()
            response = api.request(
                product["method"],
                f"invoke/{asset}/{env}/finance" + product["path"],
                headers=call_headers,
                json={"units": 3} if product["method"] == "POST" else None,
            )
            assert response.raise_for_status().json() == answer
            events = (
                api.get(
                    "audit",
                    headers={"Authorization": "Bearer " + tokens["administrator"]},
                    params={"asset_id": asset},
                )
                .raise_for_status()
                .json()
            )
            assert [e["action"] for e in reversed(events)] == [
                "register",
                "publish",
                "apply",
                "approve",
                "invoke.start",
                "invoke.end",
            ]
            assert len({e["request_id"] for e in events[:2]}) == 1
            request.node.user_properties.append(
                (
                    "finding",
                    f"{product['name']}　{product['method']} {product['path']} → {response.status_code}　{json.dumps(answer, ensure_ascii=False)}",
                )
            )
        assert [(m, p) for m, p in calls if m != "HEAD"] == [
            (item["method"], "/warehouse/v1" + item["path"]) for item in CATALOG[:6]
        ]


def test_upstream_unavailable(aws, resources, tmp_path, request):
    """承認済みのHTTPS接続先が停止したとき、502と監査・アクセスログを同じIDで追跡できる"""
    from packages.tools.demo.seed_marketplace import CATALOG, offer

    with ExitStack() as stack:
        with https_stock(aws, tmp_path, os.environ["AWS_CA_BUNDLE"]) as (binding, ca, _):
            url, tokens = stack.enter_context(
                live_portal(aws, resources, tmp_path, "upstream-stop", binding, ca)
            )
            api = stack.enter_context(httpx.Client(base_url=url + "/api/", trust_env=False))
            owner, user = ({"Authorization": "Bearer " + tokens[k]} for k in ("owner", "user"))
            asset = (
                api.post("apis", headers=owner, json={**offer(CATALOG[0]), "base_path": "/v1"})
                .raise_for_status()
                .json()["id"]
            )
            api.put(
                f"apis/{asset}/publication", params={"published": True}, headers=owner
            ).raise_for_status()
            right = (
                api.post(
                    f"apis/{asset}/requests",
                    headers=user,
                    json={"project": "finance", "environment": "production", "reason": "在庫確認"},
                )
                .raise_for_status()
                .json()
            )
            api.post(
                "requests/" + right["id"],
                headers=owner,
                json={"action": "approve", "revision": right["revision"], "reason": "用途を確認"},
            ).raise_for_status()
        call_headers = invocation_headers(api, user, endpoint="credentials")
        response = api.get(f"invoke/{asset}/production/finance/items", headers=call_headers)
        assert response.status_code == 502
        trace = response.headers["x-request-id"]
        events = api.get("audit", headers=user, params={"request_id": trace}).raise_for_status().json()
        assert [(e["action"], e["detail"]) for e in reversed(events)] == [
            ("invoke.start", "GET"),
            ("invoke.error", "502"),
        ]
        logs = http_access_records(tmp_path / "access.log")
        assert [(e["status"], e["operation"]) for e in logs if e["request_id"] == trace] == [
            (502, "/items")
        ]
        request.node.user_properties.append(
            (
                "finding",
                f"接続先停止後 GET /items → 502。開始・通信失敗・HTTPアクセスログをID {trace} で照合。",
            )
        )


def test_cognito_member_lifecycle(aws, resources, tmp_path):
    """AWS Emulatorで氏名付き招待と本人編集を行い、Cognitoの識別子とトークンが継続して使える。"""
    with live_portal(aws, resources, tmp_path, "directory") as (url, tokens):
        admin = {"Authorization": "Bearer " + tokens["administrator"]}
        claims = jwt.decode(tokens["user"], options={"verify_signature": False})
        pool = claims["iss"].split("/")[-1]
        idp = aws.client("cognito-idp")
        with httpx.Client(base_url=url + "/api/", trust_env=False) as api:
            current_members = (
                api.get("workspace/units/finance/usage", headers=admin)
                .raise_for_status()
                .json()["members"]
            )
            assert any(r["username"] == "user" for r in current_members)
            username = "account@example.org"
            created = api.post(
                "members",
                json={
                    "email": username,
                    "role": "consumer",
                    "project": "finance",
                    "full_name": "河合 直子",
                },
                headers=admin,
            )
            assert created.status_code == 201, created.text
            member = created.json()
            assert (member["email"], member["full_name"], member["display_name"]) == (
                username,
                "河合 直子",
                None,
            )
            initial = idp.admin_get_user(UserPoolId=pool, Username=username)
            assert initial["Username"] == member["username"] == username
            assert {"Name": "sub", "Value": member["subject"]} in initial["UserAttributes"]
            assert any(
                row["subject"] == member["subject"]
                for row in api.get("members", headers=admin).json()["items"]
            )
            password = secrets.token_urlsafe(24) + "9aA!"
            idp.admin_set_user_password(
                UserPoolId=pool, Username=username, Password=password, Permanent=True
            )
            token = idp.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=claims["client_id"],
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )["AuthenticationResult"]["AccessToken"]
            user = {"Authorization": "Bearer " + token}
            assert api.get("me", headers=user).json()["projects"] == ["finance"]
            profile = api.get("me/profile", headers=user).raise_for_status().json()
            assert (profile["subject"], profile["revision"]) == (member["subject"], 1)
            edited = (
                api.patch(
                    "me/profile",
                    json={"revision": 1, "display_name": "なお"},
                    headers=user,
                )
                .raise_for_status()
                .json()
            )
            assert (edited["full_name"], edited["display_name"], edited["revision"]) == (
                "河合 直子",
                "なお",
                2,
            )
            after = idp.admin_get_user(UserPoolId=pool, Username=username)
            assert (after["Username"], after["UserAttributes"]) == (
                initial["Username"],
                initial["UserAttributes"],
            )
            assert api.get("me", headers=user).json()["subject"] == member["subject"]
            workspace = api.get("workspace", headers=admin).raise_for_status().json()
            row = next(r for r in workspace["memberships"] if r["subject"] == member["subject"])
            assert (row["email"], row["full_name"], row["display_name"]) == (
                username,
                "河合 直子",
                "なお",
            )
            assert api.delete(
                "members/" + member["subject"], params={"username": username}, headers=admin
            ).is_success
            assert api.get("me", headers=user).status_code == 403
            with pytest.raises(idp.exceptions.UserNotFoundException):
                idp.admin_get_user(UserPoolId=pool, Username=username)
