import json
import os
import ssl
import subprocess
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.sync_api import expect, sync_playwright

from tests.support.catalog import headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal


@contextmanager
def delivery_service(folder):
    calls = []

    class Delivery(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            path = urlsplit(self.path)
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            calls.append((path.path, parse_qs(path.query), body, self.headers.get("x-request-id")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"cost": body["packages"] * 350, "currency": "JPY"}).encode())

    cert, private = folder / "cert.pem", folder / "private.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-out",
            str(cert),
            "-keyout",
            str(private),
        ],
        check=True,
        capture_output=True,
    )
    with ThreadingHTTPServer(("127.0.0.1", 0), Delivery) as httpd:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, private)
        httpd.socket = tls.wrap_socket(httpd.socket, server_side=True)
        worker = Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            yield {"kind": "https", "address": f"https://127.0.0.1:{httpd.server_port}"}, cert, calls
        finally:
            httpd.shutdown()
            worker.join()


def delivery_spec():
    packages = {
        "type": "object",
        "required": ["packages"],
        "properties": {"packages": {"type": "integer", "minimum": 1}},
    }
    quote = {
        "type": "object",
        "properties": {"cost": {"type": "integer"}, "currency": {"type": "string"}},
    }
    return {
        "openapi": "3.0.3",
        "info": {"title": "配送見積", "version": "1.0"},
        "components": {
            "parameters": {
                "ParcelId": {
                    "name": "parcel",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            },
            "schemas": {"Packages": packages, "Quote": quote},
        },
        "paths": {
            "/parcels/{parcel}/estimate": {
                "parameters": [{"$ref": "#/components/parameters/ParcelId"}],
                "post": {
                    "summary": "配送料を計算",
                    "description": "荷物の個数から送料を計算します。",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "details",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Packages"}}
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "見積金額",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Quote"}}
                            },
                        }
                    },
                },
            }
        },
    }


def test_openapi_key_console(tmp_path, request):
    """OpenAPIの型からパス・クエリ・JSONを入力し、選択したキーでHTTPSの送料計算を実行する"""
    with delivery_service(tmp_path) as (target, cert, calls):
        config = tmp_path / "settings.json"
        config.write_text(
            json.dumps(
                {"targets": {"deliver-test": {**target, "owner": "supply", "environment": "sandbox"}}}
            )
        )
        env = {
            **os.environ,
            "TSUGITE_DEMO": "1",
            "HUB_SETTINGS_FILE": str(config),
            "SSL_CERT_FILE": str(cert),
            "DATABASE_URL": "sqlite:///" + str(tmp_path / "app.db"),
        }
        with serve_portal(env) as portal, httpx.Client(base_url=portal, trust_env=False) as api:
            owner, consumer = (headers(api, p) for p in ("provider", "consumer"))
            asset = (
                api.post(
                    "/api/apis",
                    headers=owner,
                    json={
                        "name": "配送見積API",
                        "summary": "梱包数から送料を取得",
                        "owner": "supply",
                        "targets": {"sandbox": "deliver-test"},
                        "spec": delivery_spec(),
                    },
                )
                .raise_for_status()
                .json()["id"]
            )
            base = "/api/apis/" + asset
            api.put(base + "/publication?published=true", headers=owner).raise_for_status()
            grant = (
                api.post(
                    base + "/requests",
                    headers=consumer,
                    json={"project": "finance", "environment": "sandbox", "reason": "運賃の概算"},
                )
                .raise_for_status()
                .json()
            )
            api.post(
                "/api/requests/" + grant["id"],
                headers=owner,
                json={"action": "approve", "revision": grant["revision"], "reason": "用途確認"},
            ).raise_for_status()
            key = (
                api.post(
                    "/api/keys",
                    headers=consumer,
                    json={
                        "project": "finance",
                        "name": "配送の検証",
                        "kind": "personal",
                        "api_ids": [asset],
                    },
                )
                .raise_for_status()
                .json()
            )

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                with browser_evidence(request.node, "api-docs", page, page) as capture:
                    page.goto(portal)
                    page.get_by_role("button", name="利用チーム", exact=True).click()
                    navigate(page, "APIカタログ")
                    page.get_by_role("link", name="配送見積API").click()
                    docs = page.get_by_role("heading", name="API Docs", exact=True).locator("..")
                    docs.get_by_text("POST /parcels/{parcel}/estimate　配送料を計算", exact=True).click()
                    schemas = docs.get_by_text("application/json のスキーマ", exact=True)
                    schemas.first.click()
                    expect(docs.locator("pre").filter(has_text='"packages"').first).to_be_visible()
                    schemas.nth(1).click()
                    expect(docs.locator("pre").filter(has_text='"currency"').first).to_be_visible()
                    docs.get_by_role("heading", name="API Docs").scroll_into_view_if_needed()
                    capture(
                        page,
                        "specification",
                        "OpenAPIの参照を解決した配送見積のパラメータ・入力と応答のスキーマ",
                    )
                    schemas.first.click()
                    schemas.nth(1).click()
                    docs.get_by_label("利用するAPIキーと環境").select_option(
                        label="配送の検証（個人） · finance · 検証"
                    )
                    docs.get_by_label("parcel（path）").fill("JP17")
                    docs.get_by_label("details（query）").fill('["price","arrival"]')
                    docs.get_by_label("送信するリクエスト本文").fill('{"packages":3}')
                    run = docs.get_by_role("button", name="選んだキーで実行")
                    with page.expect_response(lambda r: "/invoke/" in r.url) as invocation:
                        run.click()
                    assert invocation.value.status == 200
                    trace = invocation.value.headers["x-request-id"]
                    expect(docs.locator('pre[aria-live="polite"]')).to_contain_text(trace)
                    expect(docs.locator('pre[aria-live="polite"]')).to_contain_text('"cost": 1050')
                    assert calls == [
                        (
                            "/parcels/JP17/estimate",
                            {"details": ["price", "arrival"]},
                            {"packages": 3},
                            trace,
                        )
                    ]
                    capture(
                        page,
                        "response",
                        "選んだ個人キーでHTTPSの配送見積を呼び出し、3個分の1,050円とリクエストIDを確認",
                    )
                    api.delete("/api/keys/" + key["id"], headers=consumer).raise_for_status()
                    run.click()
                    expect(docs.locator('pre[aria-live="polite"]')).to_contain_text("HTTP 401")
                    assert len(calls) == 1
                    capture(
                        page,
                        "revoked",
                        "同じ画面のキーを失効させて再実行。HTTP 401で停止し、配送見積への転送は計1回",
                    )
                browser.close()
            request.node.user_properties.append(
                (
                    "finding",
                    "ブラウザーのAPI Docsで個人キーを選び、パス・クエリ・JSON本文を入力。HTTPS接続先で受け取った3個に対し1,050円を計算。応答と接続先のリクエストIDを照合し、キー失効後の転送が0件であることを確認。",
                )
            )
