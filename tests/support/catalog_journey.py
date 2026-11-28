"""商品登録から利用までの共通テスト操作を提供する。"""

import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, suppress

import pytest
from playwright.sync_api import Locator, Page, expect, sync_playwright
from pytest_given import given, then, when

from tests.support.portal_server import ROOT
from tests.support.screenshots import capture_image


@contextmanager
def browser_evidence(
    case: pytest.Item, mode: str, provider: Page, consumer: Page
) -> Iterator[Callable[[Page | Locator, str, str], None]]:
    def capture(view: Page | Locator, name: str, caption: str) -> None:
        capture_image(case, mode, view, name, caption)

    try:
        yield capture
    except Exception:
        for name, page in (("提供者", provider), ("利用者", consumer)):
            with suppress(Exception):
                capture(page, "failure-" + name, "失敗時の" + name + "画面")
        raise


def navigate(page: Page, label: str) -> None:
    toggle = page.get_by_role("button", name="ナビゲーション", exact=True)
    expect(toggle).to_be_visible()
    if toggle.get_attribute("aria-expanded") == "false":
        toggle.click()
    page.get_by_role("navigation", name="ポータル").get_by_role("button", name=label, exact=True).click()


def approve_in_browser(browser, owner, url, title, tokens=None):
    expect(owner.get_by_role("button", name="公開申請を取り下げる")).to_be_visible()
    admin = browser.new_page()
    admin.goto(url)
    if tokens:
        admin.evaluate("(token) => sessionStorage.setItem('access', token)", tokens["administrator"])
        admin.reload()
    else:
        admin.get_by_role("button", name="管理者", exact=True).click()
    navigate(admin, "届いた申請")
    admin.get_by_role("link", name=title, exact=True).click()
    admin.get_by_label("公開判断の理由").fill("用途と接続仕様を確認")
    admin.get_by_role("button", name="公開申請を承認", exact=True).click()
    expect(admin.get_by_role("button", name="公開申請を承認")).to_have_count(0)
    admin.close()
    owner.reload()


def catalog_journey(
    url: str, case: pytest.Item, tokens: dict[str, str] | None = None, consumer_subject: str = "consumer"
) -> None:
    with sync_playwright() as playwright, ExitStack() as evidence:
        browser = playwright.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH") or None,
            args=["--no-zygote", "--disable-gpu", "--disable-software-rasterizer"],
        )
        provider = browser.new_page()
        consumer = browser.new_page(viewport={"width": 390, "height": 844})
        capture = evidence.enter_context(
            browser_evidence(case, "cognito" if tokens else "demo", provider, consumer)
        )
        remote_requests = []
        for page in (provider, consumer):
            page.on(
                "request",
                lambda r: (
                    remote_requests.append(r.url)
                    if r.url.startswith(("http://", "https://")) and not r.url.startswith(url + "/")
                    else None
                ),
            )
            page.goto(url)
        with given("提供チームがOpenAPIと接続先を登録して公開する"):
            if tokens:
                for page, identity in ((provider, "owner"), (consumer, "user")):
                    page.evaluate("(token) => sessionStorage.setItem('access', token)", tokens[identity])
                    page.reload()
            else:
                provider.get_by_role("button", name="提供チーム", exact=True).click()
            navigate(provider, "提供するAPI")
            provider.get_by_role("button", name="APIを登録", exact=True).click()
            provider.get_by_label("API名", exact=True).fill("棚卸API")
            provider.get_by_label("API識別名", exact=True).fill("stock-lookup")
            provider.get_by_label("用途・説明").fill("倉庫の在庫を照会する")
            provider.get_by_label("検証の接続先").select_option("sample-sandbox")
            provider.get_by_label("本番の接続先", exact=True).select_option("sample-production")
            provider.get_by_label("OpenAPIファイル").set_input_files(
                ROOT / "docs/examples/stock.openapi.json"
            )
            provider.get_by_role("button", name="下書きを保存").click()
            expect(provider.get_by_role("button", name="公開申請する")).to_be_visible()
            capture(provider, "draft", "提供者が保存した公開前の下書き")
            provider.get_by_role("button", name="公開申請する").click()
            approve_in_browser(browser, provider, url, "棚卸API", tokens)
            expect(provider.get_by_role("button", name="掲載を取り下げる")).to_be_visible()
            capture(provider, "01-published", "提供者が公開した棚卸APIとOpenAPIの操作仕様")
        with when("利用チームが検索して申請し、提供チームが承認する"):
            if not tokens:
                consumer.get_by_role("button", name="利用チーム", exact=True).click()
            navigate(consumer, "APIカタログ")
            consumer.locator("summary").filter(has_text="検索条件").click()
            consumer.get_by_label("キーワードで検索").fill("在庫一覧を取得")
            consumer.get_by_role("button", name="検索", exact=True).click()
            expect(consumer.get_by_role("link", name="棚卸API")).to_be_visible()
            capture(consumer, "02-search", "OpenAPIの操作名「在庫一覧を取得」で見つかったAPI")
            consumer.get_by_role("link", name="棚卸API").click()
            consumer.get_by_role("link", name="利用申請へ進む").click()
            consumer.get_by_label("利用目的").fill("月末の棚卸し")
            consumer.get_by_role("button", name="申請する").click()
            expect(
                consumer.get_by_role("row")
                .filter(has_text="finance · 検証")
                .get_by_text("承認待ち", exact=True)
            ).to_be_visible()
            capture(consumer, "03-pending", "利用チームの申請が検証環境で承認待ちになった状態")
            navigate(provider, "届いた申請")
            provider.get_by_label("判断・取下げの理由").fill("対象の倉庫を記載してください")
            provider.get_by_role("button", name="却下", exact=True).click()
            expect(provider.get_by_text("finance · 検証 · 却下")).to_be_visible()
            capture(provider, "04-rejected", "提供者が最初の申請を却下した結果")
            navigate(consumer, "自分の申請")
            expect(consumer.get_by_text("判断理由　対象の倉庫を記載してください")).to_be_visible()
            expect(consumer.get_by_role("button", name="APIを開く")).to_have_count(0)
            capture(consumer, "04b-reason", "利用者が却下理由を読み、再申請前に確認できる")

            navigate(consumer, "APIカタログ")
            consumer.get_by_role("link", name="棚卸API").click()
            consumer.get_by_role("link", name="利用申請へ進む").click()
            consumer.get_by_label("利用プロジェクト").select_option("finance")
            consumer.locator("#environment").select_option("sandbox")
            consumer.get_by_label("利用目的").fill("岐阜倉庫の月末棚卸し")
            consumer.get_by_role("button", name="申請する").click()
            expect(
                consumer.get_by_role("row")
                .filter(has_text="finance · 検証")
                .get_by_text("承認待ち", exact=True)
            ).to_be_visible()
            navigate(provider, "届いた申請")
            provider.get_by_label("判断・取下げの理由").fill("用途を確認")
            provider.get_by_role("button", name="承認", exact=True).click()
            expect(provider.get_by_role("button", name="権限を取り消す")).to_be_visible()
            capture(provider, "05-approved", "利用目的を追記した再申請に権限が付与された状態")
        with then("利用チームはスマートフォン幅でAPIを呼べる"):
            navigate(consumer, "自分の申請")
            consumer.get_by_role("button", name="APIを開く").click()
            expect(consumer.get_by_role("heading", name="API Docs")).to_be_visible()
            item = consumer.locator(".doc-operation").filter(
                has=consumer.locator("summary", has_text="GET /items/{sku}")
            )
            item.locator("summary").first.click()
            run = item.get_by_role("button", name="短期認証で呼び出す")
            run.click()
            expect(item.get_by_text("sku を入力してください")).to_be_visible()
            item.get_by_label("sku（path）").fill("TS-01")
            with consumer.expect_response(
                lambda r: r.url.endswith("/invoke/stock-lookup/sandbox/finance/items/TS-01")
            ) as invoked:
                run.click()
            assert invoked.value.status == 200
            output = item.get_by_text("HTTP 200", exact=False)
            expect(output).to_contain_text("TS-01")
            expect(item.locator("pre").filter(has_text="curl")).to_contain_text(
                "/invoke/stock-lookup/sandbox/finance/items/TS-01"
            )
            capture(
                output,
                "06-invoked",
                "SKUを指定し、API Docs内で短期認証を発行して得たHTTPステータスと応答本文",
            )
            contrast = output.evaluate(r"""element => {
                const style = getComputedStyle(element);
                function luminance(rgb) {
                    const [r,g,b] = rgb.match(/\d+/g).slice(0,3).map(channel => {
                        const v = Number(channel) / 255;
                        return v <= 0.04045 ? v/12.92 : ((v+0.055)/1.055)**2.4;
                    });
                    return 0.2126*r + 0.7152*g + 0.0722*b;
                }
                const a = luminance(style.color), b = luminance(style.backgroundColor);
                return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
            }""")
            assert contrast >= 4.5
            assert consumer.evaluate("document.documentElement.scrollWidth <= innerWidth")
        with when("掲載を取り下げると新規申請が止まり、承認済みの利用は続く"):
            consumer.get_by_role("link", name="利用申請へ進む").click()
            expect(consumer.get_by_label("利用目的")).to_be_visible()
            navigate(provider, "提供するAPI")
            provider.get_by_role("link", name="棚卸API").click()
            provider.get_by_role("button", name="掲載を取り下げる").click()
            expect(provider.get_by_role("button", name="公開申請する")).to_be_visible()
            consumer.locator("#environment").select_option("production")
            consumer.get_by_label("利用目的").fill("本番の在庫照会")
            consumer.get_by_role("button", name="申請する").click()
            expect(consumer.get_by_role("alert")).to_contain_text("409")
            capture(
                consumer.get_by_role("alert"), "07-unlisted", "掲載取り下げ後の新規申請に対する拒否理由"
            )
            navigate(consumer, "APIカタログ")
            expect(consumer.get_by_text("該当するAPIはありません。")).to_be_visible()
            navigate(consumer, "自分の申請")
            consumer.get_by_role("button", name="APIを開く").click()
            expect(consumer.get_by_role("button", name="申請する")).to_have_count(0)
            consumer.get_by_role("button", name="認証して実行").click()
            expect(consumer.get_by_text("HTTP 200", exact=False)).to_be_visible()
        with when("提供者が権限を取り消す"):
            navigate(provider, "届いた申請")
            provider.get_by_label("判断・取下げの理由").fill("棚卸し完了")
            provider.get_by_role("button", name="権限を取り消す").click()
            expect(provider.get_by_text("finance · 検証 · 取消済み")).to_be_visible()
        with then("同じ利用画面からの再実行を拒否し、業務操作履歴に記録する"):
            consumer.get_by_role("button", name="認証して実行").click()
            expect(consumer.get_by_text("HTTP 403", exact=False)).to_be_visible()
            capture(
                consumer.get_by_text("HTTP 403", exact=False),
                "08-revoked",
                "権限を取り消した後、同じ利用者の呼び出しを拒否",
            )
            consumer.get_by_role("button", name="この実行の業務操作履歴").click()
            expect(consumer.locator(".result-table tbody tr")).to_have_count(1)
            expect(consumer.locator(".result-table tbody tr")).to_contain_text("呼び出し拒否")
            capture(consumer, "08b-trace", "取消後の403からリクエストIDで特定した監査記録")
            navigate(provider, "業務操作履歴")
            expect(
                provider.get_by_role("row")
                .filter(has_text="invoke.denied")
                .filter(has_text=consumer_subject)
            ).to_have_count(0)
            expect(
                provider.get_by_role("row")
                .filter(has=provider.get_by_text("apply", exact=True))
                .filter(has_text=consumer_subject)
                .first
            ).to_be_visible()
            capture(provider, "09-audit", "利用者・操作・リクエストIDを表示した業務操作履歴")
            assert remote_requests == []
        browser.close()
