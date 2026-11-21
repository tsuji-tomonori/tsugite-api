import os
from contextlib import ExitStack, contextmanager, suppress

from playwright.sync_api import expect, sync_playwright
from pytest_given import given, then, when

from tests.portal_server import ROOT


@contextmanager
def browser_evidence(case, mode, provider, consumer):
    folder = ROOT / "artifacts" / "screenshots" / mode
    folder.mkdir(parents=True, exist_ok=True)

    def capture(view, name, caption):
        path = folder / (name + ".png")
        view.screenshot(path=path, animations="disabled")
        case.user_properties.append(
            ("screenshot", str(path.relative_to(ROOT / "artifacts")) + "|" + caption)
        )

    try:
        yield capture
    except Exception:
        for name, page in (("提供者", provider), ("利用者", consumer)):
            with suppress(Exception):
                capture(page, "failure-" + name, "失敗時の" + name + "画面")
        raise


def catalog_journey(url, case, tokens=None, consumer_subject="consumer"):
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
            provider.get_by_role("button", name="提供するAPI").click()
            provider.get_by_label("API名", exact=True).fill("棚卸API")
            provider.get_by_label("用途・説明").fill("倉庫の在庫を照会する")
            provider.get_by_label("検証の接続先").select_option("sample-sandbox")
            provider.get_by_label("本番の接続先").select_option("sample-production")
            provider.get_by_label("OpenAPIファイル").set_input_files(
                ROOT / "examples/stock.openapi.json"
            )
            provider.get_by_role("button", name="下書きを保存").click()
            provider.get_by_role("button", name="公開する").click()
            expect(provider.get_by_role("button", name="掲載を取り下げる")).to_be_visible()
            capture(provider, "01-published", "提供者が公開した棚卸APIとOpenAPIの操作仕様")
        with when("利用チームが検索して申請し、提供チームが承認する"):
            if not tokens:
                consumer.get_by_role("button", name="利用チーム", exact=True).click()
            consumer.get_by_role("button", name="APIカタログ", exact=True).click()
            consumer.get_by_label("キーワードで検索").fill("在庫一覧を取得")
            consumer.get_by_role("button", name="検索", exact=True).click()
            expect(consumer.get_by_role("button", name="詳細を見る")).to_be_visible()
            capture(consumer, "02-search", "OpenAPIの操作名「在庫一覧を取得」で見つかったAPI")
            consumer.get_by_role("button", name="詳細を見る").click()
            consumer.get_by_label("利用目的").fill("月末の棚卸し")
            consumer.get_by_role("button", name="申請する").click()
            expect(consumer.get_by_text("finance · 検証 · 承認待ち")).to_be_visible()
            capture(consumer, "03-pending", "利用チームの申請が検証環境で承認待ちになった状態")
            provider.get_by_role("button", name="届いた申請").click()
            provider.get_by_label("判断・取下げの理由").fill("対象の倉庫を記載してください")
            provider.get_by_role("button", name="却下", exact=True).click()
            expect(provider.get_by_text("finance · 検証 · 却下")).to_be_visible()
            capture(provider, "04-rejected", "提供者が最初の申請を却下した結果")
            consumer.get_by_role("button", name="APIカタログ", exact=True).click()
            consumer.get_by_role("button", name="詳細を見る").click()
            consumer.get_by_label("利用プロジェクト").select_option("finance")
            consumer.locator("#environment").select_option("sandbox")
            consumer.get_by_label("利用目的").fill("岐阜倉庫の月末棚卸し")
            consumer.get_by_role("button", name="申請する").click()
            expect(consumer.get_by_text("finance · 検証 · 承認待ち")).to_be_visible()
            provider.get_by_role("button", name="届いた申請").click()
            provider.get_by_label("判断・取下げの理由").fill("用途を確認")
            provider.get_by_role("button", name="承認", exact=True).click()
            expect(provider.get_by_role("button", name="権限を取り消す")).to_be_visible()
            capture(provider, "05-approved", "利用目的を追記した再申請に権限が付与された状態")
        with then("利用チームはスマートフォン幅でAPIを呼べる"):
            consumer.get_by_role("button", name="自分の申請").click()
            consumer.get_by_role("button", name="APIを開く").click()
            expect(consumer.get_by_role("button", name="実行する")).to_be_visible()
            consumer.reload()
            consumer.get_by_role("button", name="実行する").click()
            expect(consumer.get_by_text("HTTP 200", exact=False)).to_be_visible()
            if tokens:
                expect(consumer.get_by_text("TS-01", exact=False)).to_be_visible()
            capture(
                consumer.get_by_text("HTTP 200", exact=False),
                "06-invoked",
                "承認済みの呼び出しが返したHTTPステータスと応答本文",
            )
            output = consumer.get_by_text("HTTP 200", exact=False)
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
            provider.get_by_role("button", name="提供するAPI").click()
            provider.get_by_role("button", name="詳細を見る").click()
            provider.get_by_role("button", name="掲載を取り下げる").click()
            expect(provider.get_by_role("button", name="公開する")).to_be_visible()
            consumer.locator("#environment").select_option("production")
            consumer.get_by_label("利用目的").fill("本番の在庫照会")
            consumer.get_by_role("button", name="申請する").click()
            expect(consumer.get_by_role("alert")).to_contain_text("409")
            capture(
                consumer.get_by_role("alert"), "07-unlisted", "掲載取り下げ後の新規申請に対する拒否理由"
            )
            consumer.get_by_role("button", name="APIカタログ", exact=True).click()
            expect(consumer.get_by_text("該当するAPIはありません。")).to_be_visible()
            consumer.get_by_role("button", name="自分の申請").click()
            consumer.get_by_role("button", name="APIを開く").click()
            expect(consumer.get_by_role("button", name="申請する")).to_have_count(0)
            consumer.get_by_role("button", name="実行する").click()
            expect(consumer.get_by_text("HTTP 200", exact=False)).to_be_visible()
        with when("提供者が権限を取り消す"):
            provider.get_by_role("button", name="届いた申請").click()
            provider.get_by_label("判断・取下げの理由").fill("棚卸し完了")
            provider.get_by_role("button", name="権限を取り消す").click()
            expect(provider.get_by_text("finance · 検証 · 取消済み")).to_be_visible()
        with then("同じ利用画面からの再実行を拒否し、監査履歴に記録する"):
            consumer.get_by_role("button", name="実行する").click()
            expect(consumer.get_by_text("HTTP 403", exact=False)).to_be_visible()
            capture(
                consumer.get_by_text("HTTP 403", exact=False),
                "08-revoked",
                "権限を取り消した後、同じ利用者の呼び出しを拒否",
            )
            provider.get_by_role("button", name="監査履歴").click()
            expect(provider.get_by_text(f"invoke.denied · {consumer_subject}")).to_be_visible()
            capture(provider, "09-audit", "利用者・操作・リクエストIDを表示した監査履歴")
            assert remote_requests == []
        browser.close()
