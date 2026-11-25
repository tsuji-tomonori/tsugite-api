# 提供者が利用者の操作を選び、送料1,400円のHTTPS応答と権限変更直後の転送停止を照合する。
import json
import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.browser.test_api_docs import delivery_service, delivery_spec
from tests.support.catalog import headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal


def test_person_operation_console(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """提供者が利用者の操作を選び、送料1,400円のHTTPS応答と権限変更直後の転送停止を照合する"""
    spec = delivery_spec()
    path = "/parcels/{parcel}/estimate"
    item = spec["paths"][path]
    item["get"] = {"summary": "見積を閲覧", "responses": {"200": {"description": "参照完了"}}}
    item["delete"] = {"summary": "見積を削除", "responses": {"200": {"description": "削除完了"}}}
    with delivery_service(tmp_path) as (target, cert, calls):
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps(
                {"targets": {"delivery-test": {**target, "owner": "supply", "environment": "sandbox"}}}
            )
        )
        env = {
            **os.environ,
            "HUB_SETTINGS_FILE": str(cfg),
            "TSUGITE_DEMO": "1",
            "SSL_CERT_FILE": str(cert),
            "DATABASE_URL": "sqlite:///" + str(tmp_path / "operations.db"),
        }
        with (
            serve_portal(env) as url,
            httpx.Client(base_url=url, trust_env=False) as api,
            sync_playwright() as pw,
        ):
            provider, consumer = (headers(api, u) for u in ("provider", "consumer"))
            asset = (
                api.post(
                    "/api/apis",
                    headers=provider,
                    json={
                        "name": "配送見積",
                        "slug": "delivery-estimate",
                        "summary": "配送する荷物の料金を見積もります。",
                        "owner": "supply",
                        "targets": {"sandbox": "delivery-test"},
                        "spec": spec,
                    },
                )
                .raise_for_status()
                .json()["id"]
            )
            api.put(f"/api/apis/{asset}/publication?published=true", headers=provider).raise_for_status()
            grant = (
                api.post(
                    f"/api/apis/{asset}/requests",
                    headers=consumer,
                    json={"project": "finance", "environment": "sandbox", "reason": "料金の計算"},
                )
                .raise_for_status()
                .json()
            )
            api.post(
                "/api/requests/" + grant["id"],
                headers=provider,
                json={"action": "approve", "reason": "見積の検算", "revision": grant["revision"]},
            ).raise_for_status()
            credential = (
                api.post(
                    "/api/credentials",
                    headers=consumer,
                    json={
                        "mode": "app",
                        "name": "送料計算アプリ",
                        "project": "finance",
                        "kind": "personal",
                        "ttl_minutes": 30,
                        "refresh_minutes": 15,
                        "api_ids": [asset],
                        "operations": {asset: ["POST " + path, "DELETE " + path]},
                        "users": [],
                    },
                )
                .raise_for_status()
                .json()
            )
            browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
            owner, user = (browser.new_page(viewport={"width": 1440, "height": 980}) for _ in range(2))
            with browser_evidence(request.node, "operation-permissions", owner, user) as capture:
                owner.goto(url)
                owner.get_by_role("button", name="提供チーム", exact=True).click()
                navigate(owner, "提供するAPI")
                owner.get_by_role("link", name="配送見積", exact=True).click()
                panel = owner.locator("details").filter(
                    has=owner.locator("summary").filter(has_text="利用者ごとの操作権限")
                )

                def open_policy() -> None:
                    if panel.get_attribute("open") is None:
                        panel.locator("summary").first.click()

                open_policy()
                panel.get_by_label("対象の利用者").select_option("consumer")
                panel.get_by_role("button", name="権限を表示").click()
                open_policy()
                panel.get_by_role("button", name="参照だけを選ぶ").click()
                expect(panel.get_by_role("checkbox", name="GET " + path)).to_be_checked()
                expect(panel.get_by_role("checkbox", name="DELETE " + path)).not_to_be_checked()
                panel.get_by_role("checkbox", name="POST " + path).check()
                with owner.expect_response(
                    lambda r: r.url.endswith("/operation-policy") and r.request.method == "PUT"
                ) as saved_policy:
                    panel.get_by_role("button", name="選んだ操作を保存").click()
                assert saved_policy.value.status == 200
                expect(owner.get_by_text("consumer の操作権限を保存しました")).to_be_visible()
                open_policy()
                expect(panel.get_by_text("現在の設定　個別設定 · 2 操作を許可")).to_be_visible()
                panel.scroll_into_view_if_needed()
                capture(
                    owner, "selected", "提供者が利用者の見積参照・計算を許可し、削除を除外した操作権限"
                )
                user.goto(url)
                user.get_by_role("button", name="利用チーム", exact=True).click()
                navigate(user, "APIカタログ")
                user.get_by_role("link", name="配送見積", exact=True).click()
                docs = user.get_by_role("heading", name="API Docs", exact=True).locator("..")
                expect(docs.locator("summary").filter(has_text="GET " + path)).to_have_count(0)
                expect(docs.locator("summary").filter(has_text="DELETE " + path)).to_have_count(0)
                docs.get_by_label("parcel（path）").fill("JP17")
                docs.get_by_label("送信するリクエスト本文").fill('{"packages":4}')
                run = docs.get_by_role("button", name="認証して実行")
                with (
                    user.expect_response(
                        lambda r: "/credentials/" + credential["id"] + "/token-exchange" in r.url
                    ) as token,
                    user.expect_response(lambda r: "/invoke/" in r.url) as invocation,
                ):
                    run.click()
                assert token.value.ok and invocation.value.status == 200
                trace = invocation.value.headers["x-request-id"]
                received = invocation.value.request
                assert received.header_value("x-tsugite-key-id") is None
                matches_issued_token = (
                    received.header_value("authorization")
                    == "Bearer " + token.value.json()["access_token"]
                )
                assert matches_issued_token, "短期トークンを転送する"
                assert calls == [("/parcels/JP17/estimate", {}, {"packages": 4}, trace)]
                expect(docs.locator('pre[aria-live="polite"]')).to_contain_text('"cost": 1400')
                capture(
                    user,
                    "delegate",
                    "利用者とアプリがともに許可された見積計算を短期トークンで実行。HTTPS応答は1,400円",
                )
                panel.get_by_role("button", name="すべて外す").click()
                with owner.expect_response(
                    lambda r: r.url.endswith("/operation-policy") and r.request.method == "PUT"
                ) as saved_policy:
                    panel.get_by_role("button", name="選んだ操作を保存").click()
                assert saved_policy.value.status == 200
                expect(owner.get_by_text("consumer の操作権限を保存しました")).to_be_visible()
                assert (
                    api.get(f"/api/apis/{asset}/operation-policy", headers=provider).json()[
                        "permissions"
                    ]["consumer"]
                    == []
                )
                denied = api.post(
                    "/api/invoke/delivery-estimate/sandbox/finance/parcels/JP17/estimate",
                    headers={"Authorization": "Bearer " + token.value.json()["access_token"]},
                    json={"packages": 4},
                )
                assert denied.status_code == 403 and len(calls) == 1
                user.reload()
                expect(
                    docs.get_by_text("この利用者と認証情報で許可されている操作はありません。")
                ).to_be_visible()
            browser.close()
            request.node.user_properties.append(
                (
                    "finding",
                    "利用者に参照・計算、アプリに計算・削除を許可し、両方の範囲内である計算だけをAPI Docsに表示。新しいBearerで4個分1,400円を取得。提供者が全操作を外した後は発行済みトークンを403で拒否し、追加のHTTPS転送は0件。",
                )
            )
