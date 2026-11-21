import json
import os
from copy import deepcopy

from playwright.sync_api import expect, sync_playwright

from tests.catalog_journey import navigate
from tests.portal_server import serve_portal
from tests.test_catalog import SPEC


def test_publish_and_apply_from_product_page(tmp_path):
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "portal.db")}
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        owner, user = browser.new_page(), browser.new_page()
        owner.goto(url)
        owner.get_by_role("button", name="提供チーム", exact=True).click()
        navigate(owner, "提供するAPI")
        owner.get_by_role("button", name="APIを登録", exact=True).click()
        for name in ("sandbox", "staging", "production"):
            owner.locator("#" + name).select_option("sample-" + name)
        prod = owner.locator(".offer-editor").last
        prod.locator("summary").first.click()
        prod.get_by_label("同意を必須にする利用規約").fill("本番情報の社外送信を禁止します")
        prod.get_by_label("承認フロー").select_option("auto")
        prod.get_by_role("button", name="申請項目を追加").click()
        prod.locator(".application-field:visible").get_by_label("申請項目名").fill("テスト実施ID")
        prod.locator(".application-field:visible").get_by_label("受理する値", exact=False).fill("QA-882")
        spec = deepcopy(SPEC)
        spec["paths"]["/orders"] = {"post": {"responses": {"201": {"description": "登録"}}}}
        owner.locator("#spec-file").set_input_files(
            {"name": "stock.json", "mimeType": "application/json", "buffer": json.dumps(spec).encode()}
        )
        owner.get_by_role("button", name="保存して公開").click()
        expect(owner.get_by_role("button", name="掲載を取り下げる")).to_be_visible()
        user.goto(url)
        user.get_by_role("button", name="利用チーム", exact=True).click()
        navigate(user, "APIカタログ")
        user.get_by_role("link", name="在庫", exact=True).click()
        for title in ("POST /orders", "GET /items"):
            user.get_by_role("navigation", name="API操作一覧").get_by_role("button", name=title).click()
            expect(
                user.locator(".doc-operation[open]")
                .filter(has_text=title)
                .get_by_role("heading", name="レスポンス")
            ).to_be_visible()
        user.locator("#environment").select_option("staging")
        expect(user.get_by_label("本番の利用規約に同意する")).to_be_hidden()
        user.locator("#environment").select_option("production")
        user.get_by_label("本番の利用規約に同意する").check()
        user.get_by_label("テスト実施ID（必須）").fill("QA-882")
        user.get_by_label("利用目的").fill("受注連携")
        user.get_by_role("button", name="申請する").click()
        expect(user.get_by_text("finance · 本番 · 利用中", exact=True)).to_be_visible()
        expect(user.get_by_text("テスト実施ID　QA-882", exact=True)).to_be_visible()
        browser.close()
