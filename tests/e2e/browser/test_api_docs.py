# OpenAPIの型からパス・クエリ・JSONを入力し、選択したキーでHTTPSの送料計算を実行する。
import json
import os
import ssl
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from playwright.sync_api import Route, expect, sync_playwright

from tests.support.catalog import headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal


@contextmanager
def delivery_service(
    folder: Path,
) -> Iterator[tuple[dict[str, str], Path, list[tuple[str, dict[str, list[str]], object, str | None]]]]:
    calls = []

    class Delivery(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            self.send_response(200)
            self.end_headers()

        def do_POST(self) -> None:
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


def delivery_spec() -> dict[str, Any]:
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


def test_openapi_key_console(tmp_path: Path, request: pytest.FixtureRequest) -> None:
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
                        "slug": "delivery-estimate",
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
                    "/api/credentials",
                    headers=consumer,
                    json={
                        "project": "finance",
                        "name": "配送の検証",
                        "kind": "personal",
                        "mode": "bearer",
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
                    with page.expect_download() as spec_file:
                        page.get_by_role("button", name="OpenAPI定義をダウンロード").click()
                    assert (
                        json.loads(spec_file.value.path().read_text(encoding="utf8")) == delivery_spec()
                    )
                    expect(page.get_by_label("利用目的")).to_have_count(0)
                    # 画面幅の変更に伴うスクロールの影響を避け、両方の座標を同時に読む。
                    check_layout = """stacked => {
                        const columns = document.querySelector(".api-docs .operation-columns");
                        const definition = columns.querySelector(".operation-definition")
                            .getBoundingClientRect();
                        const consoleBox = columns.querySelector(".operation-console")
                            .getBoundingClientRect();
                        return definition.width > 0 && definition.height > 0
                            && consoleBox.width > 0 && consoleBox.height > 0
                            && (stacked ? definition.bottom <= consoleBox.top
                                        : definition.right <= consoleBox.left);
                    }"""
                    page.wait_for_function(check_layout, arg=False)
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_function(check_layout, arg=True)
                    page.set_viewport_size({"width": 1280, "height": 1000})
                    schemas = docs.get_by_text("application/json のスキーマ", exact=True)
                    schemas.first.click()
                    request_schema = schemas.first.locator("..").locator("pre")
                    expect(request_schema.locator(".json-number")).to_have_text("1")
                    schemas.nth(1).click()
                    response_schema = schemas.nth(1).locator("..").locator("pre")
                    key_token = response_schema.locator(".json-key").filter(has_text='"currency"')
                    value_token = response_schema.locator(".json-string").filter(has_text='"string"')
                    expect(key_token).to_be_visible()
                    palettes = []
                    for mode in ("dark", "light"):
                        page.get_by_label("表示モード").select_option(mode)
                        colors = tuple(
                            token.evaluate("(el) => getComputedStyle(el).color")
                            for token in (key_token, value_token)
                        )
                        assert colors[0] != colors[1]
                        palettes.append(colors)
                    assert palettes[0] != palettes[1]
                    models = docs.get_by_text("データモデル", exact=True)
                    models.click()
                    model = models.locator("..").locator("pre").first
                    expect(model.locator(".json-number")).to_have_text("1")
                    models.click()
                    response_schema.scroll_into_view_if_needed()
                    capture(
                        page,
                        "specification",
                        "OpenAPIの参照を解決した配送見積のパラメータ・入力と応答のスキーマ",
                    )
                    schemas.first.click()
                    schemas.nth(1).click()
                    docs.get_by_label("利用する認証情報と環境").select_option(
                        label="配送の検証（個人） · finance · 検証 · 短期Bearer"
                    )
                    docs.get_by_label("parcel（path）").fill("JP17")
                    docs.get_by_label("details（query）").fill('["price","arrival"]')
                    docs.get_by_label("送信するリクエスト本文").fill('{"packages":3}')
                    run = docs.get_by_role("button", name="認証して実行")
                    held: list[Route] = []
                    page.route("**/token-exchange", lambda route: held.append(route))
                    with page.expect_request(lambda req: req.url.endswith("/token-exchange")):
                        run.click()
                    busy = docs.locator('button[aria-busy="true"]')
                    expect(busy).to_be_disabled()
                    expect(busy).to_contain_text("実行中")
                    capture(
                        busy, "busy-hourglass", "送信中のボタンの右側に文字と同色の砂時計が表示される"
                    )
                    with page.expect_response(lambda r: "/invoke/" in r.url) as invocation:
                        held[0].continue_()
                    page.unroute("**/token-exchange")
                    expect(run).to_be_enabled()
                    assert invocation.value.status == 200
                    cmd = docs.locator('[id$="-curl"]')
                    expect(cmd).to_contain_text(invocation.value.url)
                    expect(cmd).to_contain_text("${ACCESS_TOKEN}")
                    expect(cmd).to_contain_text('{"packages":3}')
                    assert "tst_" not in cmd.inner_text()
                    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
                    docs.get_by_role("button", name="コマンドをコピー").click()
                    expect(docs.get_by_role("status")).to_have_text("コピーしました")
                    assert page.evaluate("navigator.clipboard.readText()") == cmd.inner_text()
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
                    navigate(page, "APIクライアント")
                    page.get_by_label("API商品", exact=True).select_option(label="配送見積API")
                    expect(page.get_by_role("button", name="この操作を実行")).to_have_count(0)
                    api.post(
                        "/api/credentials",
                        headers=consumer,
                        json={
                            "project": "finance",
                            "name": "配送アプリ",
                            "kind": "personal",
                            "mode": "app",
                            "api_ids": [asset],
                        },
                    ).raise_for_status()
                    legacy = (
                        api.post(
                            "/api/keys",
                            headers=consumer,
                            json={
                                "name": "配送用キー",
                                "kind": "personal",
                                "project": "finance",
                                "api_ids": [asset],
                            },
                        )
                        .raise_for_status()
                        .json()
                    )
                    page.reload()
                    page.get_by_label("API商品", exact=True).select_option(label="配送見積API")
                    page.get_by_label("parcel（path）").fill("JP18")
                    page.get_by_label("送信するリクエスト本文").fill('{"packages":2}')
                    page.get_by_role("button", name="この操作を実行").click()
                    expect(page.locator("#console-call-response")).to_contain_text('"cost": 700')
                    assert calls[-1][:3] == ("/parcels/JP18/estimate", {}, {"packages": 2})
                    capture(page, "console-oauth", "ログイン中の利用者が承認済みの環境で配送見積を取得")

                    endpoint = (
                        portal + "/api/invoke/delivery-estimate/sandbox/finance/parcels/JP19/estimate"
                    )
                    selected = page.get_by_label("APIキー（任意）", exact=True)
                    expect(selected).to_have_value("")
                    page.locator("#manual-url").fill(endpoint)
                    page.locator("#manual-method").select_option("POST")
                    page.locator("#manual-headers").fill("Content-Type: application/json")
                    page.locator("#manual-body").fill('{"packages":4}')
                    manual_send = page.get_by_role("button", name="指定したURLに送信")
                    for label in (
                        "配送アプリ（個人） · finance · アプリ",
                        "配送用キー（個人） · finance · APIキー",
                    ):
                        selected.select_option(label=label)
                        with page.expect_response(endpoint) as manual_result:
                            manual_send.click()
                        assert manual_result.value.status == 200
                        expect(page.locator("#manual-response")).to_contain_text('"cost": 1400')
                        assert calls[-1][:3] == ("/parcels/JP19/estimate", {}, {"packages": 4})
                    capture(
                        page,
                        "console-url-key",
                        "配送用キーを選び、秘密値を入力せずに直接指定したURLから送料を取得",
                    )
                    api.delete("/api/keys/" + legacy["id"], headers=consumer).raise_for_status()
                    manual_send.click()
                    expect(page.locator("#manual-response")).to_contain_text("HTTP 401")

                    url = "https://example.test/status"
                    page.route(
                        url,
                        lambda route: route.fulfill(
                            status=202, body="accepted", headers={"Access-Control-Allow-Origin": "*"}
                        ),
                    )
                    page.get_by_label("リクエストURL（必須）").fill(url)
                    manual_send.click()
                    expect(page.locator("#manual-response")).to_contain_text("呼び出しURLを指定")
                    selected.select_option("")
                    page.locator("#manual-method").select_option("GET")
                    page.locator("#manual-headers").fill("")
                    page.locator("#manual-body").fill("")
                    with page.expect_request(url) as outgoing:
                        page.get_by_role("button", name="指定したURLに送信").click()
                    expect(page.locator("#manual-response")).to_contain_text("HTTP 202")
                    assert "authorization" not in outgoing.value.all_headers()
                    capture(page, "console-url", "手入力したURLからの応答とHTTPステータスを表示")
                browser.close()
            request.node.user_properties.append(
                (
                    "finding",
                    "ブラウザーのAPI Docsで個人キーを選び、パス・クエリ・JSON本文を入力。HTTPS接続先で受け取った3個に対し1,050円を計算。応答と接続先のリクエストIDを照合し、キー失効後の転送が0件であることを確認。",
                )
            )
