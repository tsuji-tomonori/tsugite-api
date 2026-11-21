import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.portal_server import ROOT, serve_portal


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
    for name, group in [("owner", "own-supply"), ("user", "use-finance")]:
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
    yield {"issuer": os.environ["AWS_ENDPOINT_URL"] + "/" + pool, "portal_client": client}, tokens


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
                    "machine": token("batch", "batch", [], "hub/invoke"),
                    "no_scope": token("batch", "batch", [], "openid"),
                },
            )
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("identity", ["cognito", "machine"])
def test_approved_calls_reach_lambda(aws, resources, tmp_path, identity):
    auth = cognito_users(aws) if identity == "cognito" else machine_tokens(tmp_path)
    with auth as (config, tokens):
        function = resources["TsugiteApi/Sample/Resource"]
        config["targets"] = {
            env: {"kind": "lambda", "address": function, "owner": "supply", "environment": env}
            for env in ("sandbox", "production")
        }
        param = "/tsugite/" + identity
        aws.client("ssm").put_parameter(Name=param, Type="String", Value=json.dumps(config))
        aws.client("lambda").get_waiter("function_active_v2").wait(
            FunctionName=function, WaiterConfig={"Delay": 1, "MaxAttempts": 30}
        )
        env = {
            **os.environ,
            "TSUGITE_DEMO": "0",
            "HUB_SETTINGS_PARAMETER": param,
            "DATABASE_URL": "sqlite:///" + str(tmp_path / "catalog.db"),
        }
        with serve_portal(env) as url, httpx.Client(base_url=url + "/api/", trust_env=False) as api:

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
                "summary": "棚卸し",
                "owner": "supply",
                "targets": {"sandbox": "sandbox", "production": "production"},
                "spec": json.loads((ROOT / "examples/stock.openapi.json").read_text()),
            }
            result = api.post("apis", headers=owner, json=data)
            assert result.status_code == 201, result.text
            key = result.json()["id"]
            asset = "apis/" + key
            result = api.put(asset + "/publication?published=true", headers=owner)
            assert result.status_code == 200, result.text
            form = {"project": "finance", "environment": "sandbox", "reason": "棚卸し"}
            result = api.post(asset + "/requests", headers=user, json=form)
            assert result.status_code == 201, result.text
            right = result.json()
            path = f"invoke/{key}/sandbox/finance/items"
            assert api.get(path, headers=invoker).status_code == 403
            decide = "requests/" + right["id"]
            approval = {"action": "approve", "reason": "用途を確認", "revision": right["revision"]}
            assert api.post(decide, headers=user, json=approval).status_code == 403
            result = api.post(decide, headers=owner, json=approval)
            assert result.status_code == 200, result.text
            approved = result.json()
            assert api.get(path.replace("/finance/", "/supply/"), headers=invoker).status_code == 403
            assert api.get(path.replace("/sandbox/", "/production/"), headers=invoker).status_code == 403
            call = api.get(path, headers=invoker)
            assert call.status_code == 200, call.text
            assert call.json() == {"items": [{"sku": "TS-01", "stock": 12}]}
            audit = api.get(
                "audit", headers=owner, params={"request_id": call.headers["x-request-id"]}
            ).json()
            assert {e["action"] for e in audit} == {"invoke.start", "invoke.end"}
            for e in audit:
                assert (e["actor"], e["asset_id"], e["environment"], e["project"]) == (
                    "batch" if identity == "machine" else user_id,
                    key,
                    "sandbox",
                    "finance",
                )
                assert datetime.fromisoformat(e["at"])
            revoke = {"action": "revoke", "reason": "終了", "revision": approved["revision"]}
            assert api.post(decide, headers=owner, json=revoke).status_code == 200
            assert api.get(path, headers=invoker).status_code == 403
