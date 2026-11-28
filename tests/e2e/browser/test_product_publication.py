# 商品を公開し、利用者が商品詳細から利用申請できる。
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.catalog import SPEC
from tests.support.catalog_journey import approve_in_browser, navigate
from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


def test_publish_and_apply_from_product_page(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """商品を公開し、利用者が商品詳細から利用申請できる"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "portal.db")}
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        owner, user = browser.new_page(), browser.new_page()
        owner.goto(url)
        owner.get_by_role("button", name="提供チーム", exact=True).click()
        navigate(owner, "提供するAPI")
        owner.get_by_role("button", name="APIを登録", exact=True).click()
        owner.get_by_label("API識別名", exact=True).fill("stock-and-orders")
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
        owner.get_by_role("button", name="保存して公開申請").click()
        approve_in_browser(browser, owner, url, "在庫")
        expect(owner.get_by_role("button", name="掲載を取り下げる")).to_be_visible()
        user.goto(url)
        user.get_by_role("button", name="利用チーム", exact=True).click()
        navigate(user, "APIカタログ")
        user.get_by_role("link", name="在庫", exact=True).click()
        expect(user.get_by_role("heading", name="API操作一覧")).to_be_visible()
        orders = user.locator(".doc-operation", has_text="POST /orders")
        orders.locator("summary").first.click()
        expect(orders.get_by_role("heading", name="レスポンス")).to_be_visible()
        expect(orders.get_by_text("呼び出しには利用申請の承認が必要です。")).to_be_visible()
        expect(orders.get_by_role("button", name="短期認証で呼び出す")).to_have_count(0)
        assert user.locator("button").filter(has_text="POST /orders").count() == 0
        capture_image(request.node, "publication", user, "operations", "選んだ操作の入力と応答仕様")
        user.get_by_role("link", name="利用申請へ進む").click()
        user.locator("#environment").select_option("staging")
        expect(user.get_by_label("本番の利用規約に同意する")).to_be_hidden()
        user.locator("#environment").select_option("production")
        user.get_by_label("本番の利用規約に同意する").check()
        user.get_by_label("テスト実施ID（必須）").fill("QA-882")
        user.get_by_label("利用目的").fill("受注連携")
        user.get_by_role("button", name="申請する").click()
        expect(user.get_by_text("finance · 本番 · 利用中", exact=True)).to_be_visible()
        expect(user.get_by_text("テスト実施ID　QA-882", exact=True)).to_be_visible()
        capture_image(request.node, "publication", user, "terms", "本番の利用条件と受理された申請内容")
        browser.close()
