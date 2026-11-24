# 役割と検索語で使い方を絞り込み、手順から対象画面を開ける。
"""Exercise local hybrid search, role filters, article navigation and read-only component previews."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


def test_usage_guide(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """役割と検索語で使い方を絞り込み、手順から対象画面を開ける"""
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
            page.locator("summary").filter(has_text="検索条件").click()
            user_input = page.get_by_role("searchbox", name="何をしたいですか？")
            user_input.fill(query)
            page.get_by_label("役割", exact=True).select_option(role)
            first = page.locator("#guide-grid tr:visible a").first
            expect(first).to_have_attribute("href", "#/guide/" + article)
            first.click()
            preview = page.locator(".guide-preview")
            expect(preview).to_be_visible()
            assert preview.evaluate("el => el.inert")
            control = preview.locator("input:not([type=hidden]), select").first
            control.evaluate("el => el.focus()")
            expect(control).not_to_be_focused()
            if role == "管理者":
                email = preview.locator("#member-email")
                email.click(force=True)
                page.keyboard.type("sample")
                expect(email).to_have_value("")
                pressed = preview.locator("button").first
                pressed.evaluate("el => el.addEventListener('click', () => el.dataset.clicked = 'yes')")
                pressed.click(force=True)
                expect(pressed).not_to_have_attribute("data-clicked", "yes")
                theme = page.get_by_role("combobox", name="表示モード")
                theme.select_option("light")
                light = email.evaluate("el => getComputedStyle(el).backgroundColor")
                theme.select_option("dark")
                assert email.evaluate("el => getComputedStyle(el).backgroundColor") != light
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            capture_image(request.node, "guide", page, article, role + "が検索して開いた手順")
            page.go_back()
            page.locator("summary").filter(has_text="検索条件").click()
            expect(user_input).to_have_value(query)
            user_input.fill("unmatchedXYZ")
            expect(page.locator("#guide-empty")).to_be_visible()
            page.get_by_role("button", name="条件をクリア").click()
            expect(user_input).to_be_focused()
            cards = page.locator("#guide-grid tr:visible a")
            expect(cards).to_have_count(20)
            if role == "利用者":
                page.locator('[href="#/guide/member"]').click()
                expect(page.get_by_role("button", name="「ユーザー管理」を開く")).to_have_count(0)
                page.get_by_role("link", name="使い方ガイドの一覧に戻る").click()
            page.locator(f'[href="#/guide/{article}"]').click()
            page.get_by_role("button", name=f"「{target}」を開く").click()
            expect(page.get_by_role("heading", name=target, exact=True).first).to_be_visible()
            page.close()
        browser.close()
