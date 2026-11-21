"""Run against a fresh, migrated loopback demo database on every test."""

import os

import pytest
from pytest_given import scenario

from tests.catalog_journey import catalog_journey
from tests.portal_server import serve_portal


@pytest.fixture
def demo_url(tmp_path):
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "e2e.db")}
    with serve_portal(env) as url:
        yield url


@scenario("提供者の公開から承認・取消までを画面で操作する", tags=["CAT", "AUTH", "AUDIT"])
def test_user_flow(demo_url, request):
    catalog_journey(demo_url, request.node)


def test_large_catalog(demo_url, request):
    import httpx
    from playwright.sync_api import expect, sync_playwright

    from tests.catalog_journey import browser_evidence
    from tools.seed_marketplace import CATALOG, offer, seed

    with httpx.Client(base_url=demo_url + "/api/", trust_env=False) as api:
        ids = seed(api, 20)
        provider = {"Authorization": "Bearer " + api.post("demo/provider").json()["access_token"]}
        consumer = {"Authorization": "Bearer " + api.post("demo/consumer").json()["access_token"]}
        draft = api.post("apis", headers=provider, json=offer(CATALOG[0], 21)).raise_for_status().json()
        observed = []
        for page in range(1, 11):
            result = (
                api.get("catalog-page", params={"page": page}, headers=consumer)
                .raise_for_status()
                .json()
            )
            assert (result["total"], result["page"], len(result["items"])) == (120, page, 12)
            observed.extend(item["id"] for item in result["items"])
        assert len(set(observed)) == 120 and set(observed) == set(ids)
        assert draft["id"] not in observed
        assert (
            api.get("catalog-page", headers=provider, params={"inventory": True}).json()["total"] == 121
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        desktop = browser.new_page(viewport={"width": 1440, "height": 960})
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        with browser_evidence(request.node, "marketplace", desktop, mobile) as capture:
            for view in (desktop, mobile):
                view.goto(demo_url)
                view.get_by_role("button", name="利用チーム", exact=True).click()
                expect(view.get_by_role("heading", name="API一覧（120件）")).to_be_visible()
                expect(view.locator(".asset-card")).to_have_count(12)
                assert view.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture(desktop, "catalog", "120件の公開カタログ。先頭12件を表示するデスクトップ画面")
            capture(mobile, "phone", "390px幅で同じ公開カタログを表示")
            desktop.get_by_role("button", name="次へ").click()
            expect(desktop.get_by_text("13–24 件を表示")).to_be_visible()
            desktop.get_by_role("button", name="前へ").click()
            expect(desktop.get_by_text("1–12 件を表示")).to_be_visible()
            mobile.get_by_label("キーワードで検索").fill("岐阜")
            mobile.get_by_label("提供環境").select_option("production")
            mobile.get_by_label("提供環境").press("Tab")
            assert mobile.get_by_role("button", name="検索", exact=True).evaluate(
                "el => el.matches(':focus-visible') && getComputedStyle(el).outlineStyle !== 'none'"
            )
            mobile.keyboard.press("Enter")
            expect(mobile.get_by_role("heading", name="API一覧（3件）")).to_be_visible()
            expect(mobile.locator(".asset-card")).to_have_count(3)
            assert all("岐阜" in name for name in mobile.locator(".asset-card h3").all_text_contents())
            capture(mobile, "filtered", "キーワードと本番環境で絞り、120件から目的の3件を抽出")
            mobile.get_by_label("キーワードで検索").fill("該当なしの検索語")
            mobile.get_by_label("キーワードで検索").press("Enter")
            expect(mobile.get_by_text("該当するAPIはありません。")).to_be_visible()
            expect(mobile.locator(".asset-card")).to_have_count(0)
            capture(mobile, "empty", "該当なしを明示し、検索条件を変更できる画面")
        browser.close()
    request.node.user_properties.append(
        (
            "finding",
            "実測値：6業務×20拠点の公開120件、未公開1件。全10ページを照合し、重複・欠落・下書き混入は各0件。390pxと1440pxで横幅内に収まり、検索ボタンをキーボードで実行できた。",
        )
    )


def test_console_visual_modes(demo_url, request):
    import httpx
    from playwright.sync_api import expect, sync_playwright

    from tests.catalog_journey import browser_evidence, navigate
    from tools.seed_marketplace import seed

    with httpx.Client(base_url=demo_url + "/api/", trust_env=False) as api:
        seed(api, 1)

    def contrast(locator):
        return locator.evaluate("""element => {
            const style = getComputedStyle(element);
            let parent = element;
            while (getComputedStyle(parent).backgroundColor === 'rgba(0, 0, 0, 0)') {
                parent = parent.parentElement;
            }
            const luminance = color => color.match(/\\d+/g).slice(0,3)
                .map(n => Number(n)/255).map(n => n <= .04045 ? n/12.92 : ((n+.055)/1.055)**2.4)
                .reduce((sum, n, i) => sum+n*[.2126,.7152,.0722][i], 0);
            const a = luminance(style.color), b = luminance(getComputedStyle(parent).backgroundColor);
            return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        }""")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="light")
        with browser_evidence(request.node, "visual-modes", page, page) as capture:
            page.goto(demo_url)
            page.get_by_role("button", name="提供チーム", exact=True).click()
            link = page.locator(".asset-title").first
            expect(link).to_be_visible()
            primary = page.get_by_role("button", name="検索", exact=True)
            mode = page.get_by_label("表示モード")
            for theme, link_color in (("light", "rgb(0, 108, 224)"), ("dark", "rgb(66, 180, 255)")):
                mode.select_option(theme)
                expect(link).to_have_css("color", link_color)
                expect(primary).to_have_css("background-color", "rgb(255, 153, 0)")
                expect(primary).to_have_css("border-radius", "20px")
                expect(page.locator(".asset-card").first).to_have_css("border-radius", "16px")
                expect(page.locator(".form-select").first).to_have_css("border-radius", "8px")
                readings = [
                    (label, contrast(item))
                    for label, item in (
                        ("本文", page.locator(".description").first),
                        ("リンク", link),
                        ("主要操作", primary),
                        ("入力", page.locator("#filter-env")),
                        ("現在地", page.locator(".nav-item.active")),
                    )
                ]
                assert all(ratio >= 4.5 for _, ratio in readings)
                request.node.user_properties.append(
                    (
                        "finding",
                        theme
                        + " の文字コントラスト比　"
                        + "、".join(f"{k} {v:.2f}:1" for k, v in readings),
                    )
                )
                capture(
                    page,
                    theme,
                    "AWSコンソールの"
                    + ("ライト" if theme == "light" else "ダーク")
                    + "配色で6種類のAPIを表示",
                )
            page.reload()
            expect(mode).to_have_value("dark")
            navigate(page, "提供するAPI")
            page.get_by_role("button", name="APIを登録").click()
            page.get_by_label("API名", exact=True).fill("入力中のAPI")
            mode.select_option("light")
            expect(page.get_by_label("API名", exact=True)).to_have_value("入力中のAPI")
            page.get_by_label("すべての公開APIを検索").fill("配送")
            page.get_by_label("すべての公開APIを検索").press("Enter")
            expect(page.locator(".asset-card")).to_have_count(1)
            expect(link).to_contain_text("配送")
            mode.select_option("auto")
            page.emulate_media(color_scheme="dark")
            expect(link).to_have_css("color", "rgb(66, 180, 255)")
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload()
            navigate(page, "監査履歴")
            expect(page.locator(".audit-row").first).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture(page, "mobile-dark", "端末のダーク設定を引き継いだ390px幅の監査履歴")
            page.emulate_media(forced_colors="active")
            assert page.evaluate("matchMedia('(forced-colors: active)').matches")
            page.get_by_label("操作", exact=True).press("Tab")
            button = page.get_by_role("button", name="絞り込む")
            expect(button).to_be_focused()
            expect(button).to_have_css("outline-style", "solid")
            capture(page, "forced", "OSの強制カラーで表示した監査履歴とキーボードのフォーカス枠")
        browser.close()
