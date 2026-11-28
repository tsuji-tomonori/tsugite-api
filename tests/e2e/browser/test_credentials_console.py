# ブラウザーで3方式を発行し、実時計で1分後に更新、シークレット変更・失効まで確認する。
"""Issue tokens and change inherited lifetime from the signed-in portal."""

import hashlib
import os
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.catalog import approved, headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal


def test_credentials_console(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """ブラウザーで3方式を発行し、実時計で1分後に更新、シークレット変更・失効まで確認する"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "cred.db")}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        provider, user, admin = (headers(api, r) for r in ("provider", "consumer", "admin"))
        api.patch(
            "/api/me/profile", headers=user, json={"revision": 0, "full_name": "佐藤 花子"}
        ).raise_for_status()
        asset, _, path = approved(api, provider, user)
        api.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"unit_id": "finance", "subject": "consumer", "title": "担当", "leader": True},
        ).raise_for_status()
        api.put(
            "/api/credential-limits/apis/" + asset, headers=provider, json={"max_minutes": 30}
        ).raise_for_status()
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("dialog", lambda dialog: dialog.accept())
        result_labels = {"bearer": "試用トークン", "app": "棚卸アプリ", "system": "夜間集計"}
        with browser_evidence(request.node, "credentials", page, page) as capture:
            page.goto(url)
            page.get_by_role("button", name="利用チーム", exact=True).click()
            navigate(page, "プロジェクト")
            page.get_by_role("link", name="finance", exact=True).click()
            unit = page.locator(".box").filter(has=page.get_by_role("heading", name="利用設定"))
            unit.get_by_role("button", name="アクセストークンの上限を設定").click()
            unit.get_by_label("この範囲の上限（分）").fill("15")
            unit.get_by_role("button", name="有効期限の上限を保存").click()
            expect(page.get_by_text("有効期限の上限を保存しました")).to_be_visible()
            capture(page, "project-limit", "プロジェクトのリーダーがアクセストークンの上限を15分に設定")
            navigate(page, "APIキー")
            # Mask one-time values also for failure screenshots.
            page.add_style_tag(
                content="#credential-value-secret,#credential-value-token{color:transparent!important}"
            )
            for mode, label in result_labels.items():
                page.locator("summary").filter(has_text="認証情報を作成").click()
                page.get_by_label("発行先プロジェクト").select_option("finance")
                page.get_by_role("button", name="発行条件を確認").click()
                page.get_by_label("認証情報の名前").fill(label)
                page.get_by_label("認証方式", exact=True).select_option(mode)
                page.get_by_label("対象APIの選び方").select_option("selected")
                page.locator("#cred-api-list").get_by_label("在庫", exact=True).check()
                page.get_by_label("在庫で許可する操作").select_option("selected")
                page.get_by_label("GET /items", exact=True).check()
                if mode == "app":
                    page.get_by_label("認証情報の所有者").select_option("shared")
                    page.get_by_label("アプリを利用できる人").select_option("selected")
                    page.get_by_label("consumer（佐藤 花子）", exact=True).check()
                if mode == "system":
                    expect(page.get_by_label("認証情報の所有者")).to_be_disabled()
                ttl = page.get_by_label("トークンの有効期限（分）")
                expect(ttl).to_have_attribute("max", "15")
                ttl.fill("10")
                page.get_by_label("更新を開始できる経過時間（分）").fill(
                    "1" if mode == "bearer" else "5"
                )
                if mode == "app":
                    capture(
                        page,
                        "application-grant",
                        "利用者とOpenAPIの操作を選び、10分の有効期限と5分後の更新開始を設定",
                    )
                page.get_by_role("button", name="認証情報を発行", exact=True).click()
                output = page.locator("#credential-value-" + ("token" if mode == "bearer" else "secret"))
                expect(output).to_be_visible()
                if mode == "bearer":
                    value = output.inner_text()
                    issued_at = time.monotonic()
                    assert api.get(path, headers={"Authorization": "Bearer " + value}).is_success
                else:
                    client_id = (
                        page.locator("#credential-value-client-id").inner_text().split("　", 1)[1]
                    )
                    secret = output.inner_text()
                    token = api.post(
                        "/api/auth/token",
                        headers=user if mode == "app" else {},
                        json={"client_id": client_id, "client_secret": secret},
                    )
                    token.raise_for_status()
                    assert api.get(
                        path, headers={"Authorization": "Bearer " + token.json()["access_token"]}
                    ).is_success
                page.get_by_role("button", name="秘密の表示を閉じる").click()
                expect(output).to_have_count(0)
                expect(page.get_by_role("rowheader", name=label, exact=True)).to_be_visible()
                if mode == "bearer":
                    record = page.get_by_role("row").filter(
                        has=page.get_by_role("rowheader", name=label, exact=True)
                    )
                    record.get_by_role("button", name="アクセストークンを取得・更新").click()
                    expect(output).to_be_visible()
                    assert (
                        hashlib.sha256(output.inner_text().encode()).digest()
                        == hashlib.sha256(value.encode()).digest()
                    )
                    page.get_by_role("button", name="秘密の表示を閉じる").click()
            client = page.get_by_role("row").filter(
                has=page.get_by_role("rowheader", name="夜間集計", exact=True)
            )
            client.get_by_role("button", name="シークレットを更新").click()
            expect(page.locator("#credential-value-secret")).to_be_visible()
            page.get_by_role("button", name="秘密の表示を閉じる").click()
            expect(page.locator("#credential-value-secret")).to_have_count(0)
            assert (
                api.post(
                    "/api/auth/token", json={"client_id": client_id, "client_secret": secret}
                ).status_code
                == 401
            )
            page.set_viewport_size({"width": 1440, "height": 1440})
            capture(page, "credentials", "短期Bearer・アプリ・システム認証の一覧と対象操作、更新条件")
            live = page.get_by_role("row").filter(
                has=page.get_by_role("rowheader", name="試用トークン", exact=True)
            )
            display = page.locator("#credential-value-token")
            # Exercise the selected one-minute interval using the server's real clock.
            time.sleep(max(0, 61 - (time.monotonic() - issued_at)))
            live.get_by_role("button", name="アクセストークンを取得・更新").click()
            expect(display).to_be_visible()
            renewed = display.inner_text()
            assert hashlib.sha256(renewed.encode()).digest() != hashlib.sha256(value.encode()).digest()
            assert api.get(path, headers={"Authorization": "Bearer " + renewed}).is_success
            page.get_by_role("button", name="秘密の表示を閉じる").click()
            live.get_by_role("button", name="認証情報を失効").click()
            expect(live.get_by_text("失効済み", exact=False)).to_be_visible()
            assert api.get(path, headers={"Authorization": "Bearer " + value}).status_code in (401, 403)
            assert api.get(path, headers={"Authorization": "Bearer " + renewed}).status_code in (
                401,
                403,
            )
        browser.close()
