"""Exercise local hybrid search, role filters, article navigation and image delivery."""

import os

from playwright.sync_api import expect, sync_playwright

from tests.portal_server import serve_portal


def test_usage_guide(tmp_path):
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "guide.db")}
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        tasks = (
            ("利用チーム", "利用者", "夜間バッチから呼びたい", "credential", "APIキー"),
            ("提供チーム", "提供者", "読み取りだけ許可したい", "operations", "提供するAPI"),
            ("管理者", "管理者", "新入社員を招待したい", "member", "ユーザー管理"),
        )
        for persona, role, query, article, target in tasks:
            page = browser.new_page(viewport={"width": 390 if role == "利用者" else 1200, "height": 850})
            page.goto(url)
            page.get_by_role("button", name=persona, exact=True).click()
            page.get_by_role("link", name="使い方ガイド", exact=True).click()
            user_input = page.get_by_role("searchbox", name="何をしたいですか？")
            user_input.fill(query)
            page.get_by_label("役割", exact=True).select_option(role)
            first = page.locator("#guide-grid article:visible a").first
            expect(first).to_have_attribute("href", "#/guide/" + article)
            first.click()
            image = page.locator(".guide-article img")
            expect(image).to_be_visible()
            assert image.evaluate("(el) => el.decode().then(() => el.naturalWidth > 0)")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.go_back()
            expect(user_input).to_have_value(query)
            user_input.fill("unmatchedXYZ")
            expect(page.locator("#guide-empty")).to_be_visible()
            page.get_by_role("button", name="条件をクリア").click()
            expect(user_input).to_be_focused()
            cards = page.locator("#guide-grid article:visible a")
            expect(cards).to_have_count(20)
            if role == "利用者":
                for link in cards.all():
                    slug = link.get_attribute("href").rsplit("/", 1)[-1]
                    response = page.request.get(f"{url}/guide-images/{slug}.webp")
                    assert response.ok and response.headers["content-type"] == "image/webp"
                page.locator('[href="#/guide/member"]').click()
                expect(page.get_by_role("button", name="「ユーザー管理」を開く")).to_have_count(0)
                page.get_by_role("link", name="使い方ガイドの一覧に戻る").click()
            page.locator(f'[href="#/guide/{article}"]').click()
            page.get_by_role("button", name=f"「{target}」を開く").click()
            expect(page.get_by_role("heading", name=target, exact=True).first).to_be_visible()
            page.close()
        browser.close()
