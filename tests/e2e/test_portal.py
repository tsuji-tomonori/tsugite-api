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
