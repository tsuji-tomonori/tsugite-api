import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect, sync_playwright

from tests.support.catalog_journey import navigate
from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image
from tools.demo.seed_marketplace import seed


def assert_layout(page: Page) -> None:
    """展開後のページ幅、関連する欄の間隔、表見出しとグラフの実寸を確認する。"""
    page.evaluate("document.fonts.ready")
    page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    page.locator("details").evaluate_all("nodes => nodes.forEach(node => node.open = true)")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    for bar in page.locator(".time-bar").evaluate_all(
        "els => els.map(el => [el.getBoundingClientRect().width, el.getBoundingClientRect().height])"
    ):
        assert min(bar) >= 24, bar
    # 日本語と英数字で代替フォントが異なっても、同じ行の文字は縦方向に重なる。
    headings = page.locator(".crumb a, .resource-table thead th")
    for heading in headings.all():
        assert heading.evaluate("""el => {
            const range = document.createRange();
            range.selectNodeContents(el);
            const rects = [...range.getClientRects()];
            return rects.length && Math.max(...rects.map(r => r.top)) < Math.min(...rects.map(r => r.bottom));
        }""")
    fields = page.locator(".filter-grid > .field")
    if fields.count() > 1 and page.viewport_size["width"] == 320:
        gap = fields.first.evaluate("""el => {
            const next = el.parentElement.querySelectorAll('.field')[1];
            return next.getBoundingClientRect().top - el.getBoundingClientRect().bottom;
        }""")
        assert 16 <= gap <= 24, gap
    if page.viewport_size["width"] == 320:
        guide = page.locator(".guide-search")
        if guide.count():
            assert (
                guide.locator(".field")
                .nth(1)
                .evaluate(
                    "el => el.getBoundingClientRect().width === el.parentElement.querySelector('.field').getBoundingClientRect().width"
                )
            )
        composer = page.locator(".chat-composer")
        if composer.count():
            assert composer.locator(".field").first.evaluate(
                "el => el.getBoundingClientRect().width >= el.parentElement.clientWidth - 1"
            )


def inspect_screen(page: Page, case: pytest.Item, role: str, label: str) -> None:
    for width in (320, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        try:
            assert_layout(page)
        except AssertionError:
            capture_image(case, "layout", page, f"{role}-{label}-{width}", label)
            raise


def inspect_details(page: Page, label: str, case: pytest.Item, role: str) -> None:
    # 一覧から実際に開ける項目を使い、商品・組織の詳細と全ガイドの画面例も確認する。
    if label == "使い方ガイド":
        selector = ".guide-grid a"
    elif label == "APIカタログ":
        selector = ".asset-title"
    elif label in {"部署", "プロジェクト"}:
        selector = '.resource-table a[href*="/detail/"]'
    else:
        return
    entries = page.locator(selector).evaluate_all(
        "els => els.map(el => [el.getAttribute('href'), el.textContent])"
    )
    if label != "使い方ガイド":
        entries = entries[:1]
    for path, name in entries:
        page.locator(f'.content a[href="{path}"]').first.click()
        expected = label + "の詳細" if label in {"部署", "プロジェクト"} else name
        expect(page.locator(".content h1")).to_have_text(expected)
        expect(page.locator(".notice.error")).to_have_count(0)
        inspect_screen(page, case, role, path.replace("/", "-").lstrip("#-"))
        navigate(page, label)
        expect(page.locator(selector).first).to_be_visible()


def test_role_screen_layout(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """6種類の権限で全メニューを開き、狭幅と広幅で余白・操作領域・横あふれを検査する。"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "layout.db")}
    with serve_portal(env) as url, httpx.Client(base_url=url + "/api/", trust_env=False) as api:
        seed(api, 1)
        admin = {
            "Authorization": "Bearer " + api.post("demo/admin").raise_for_status().json()["access_token"]
        }
        api.put(
            "workspace/units/planning", headers=admin, json={"kind": "department", "name": "業務企画部"}
        ).raise_for_status()
        roles = ["consumer", "provider", "admin", "auditor"]
        for unit in ("planning", "finance"):
            email = unit + "@example.org"
            member = (
                api.post(
                    "members",
                    headers=admin,
                    json={"email": email, "role": "consumer", "project": "finance"},
                )
                .raise_for_status()
                .json()
            )
            api.put(
                "workspace/memberships",
                headers=admin,
                json={"subject": member["subject"], "unit_id": unit, "leader": True},
            ).raise_for_status()
            roles.append(email)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
            for role in roles:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                token = api.post("demo/" + role).raise_for_status().json()["access_token"]
                page.goto(url)
                page.evaluate("token => sessionStorage.setItem('access', token)", token)
                page.reload()
                nav = page.get_by_role("navigation", name="ポータル")
                expect(nav).to_be_visible(timeout=30000)
                labels = nav.get_by_role("button").all_text_contents()
                assert labels
                for label in labels:
                    navigate(page, label)
                    expect(nav.locator('[aria-current="page"]')).to_have_text(label)
                    expect(page.locator(".notice.error")).to_have_count(0)
                    inspect_screen(page, request.node, role, label)
                    inspect_details(page, label, request.node, role)
                page.close()
            browser.close()
