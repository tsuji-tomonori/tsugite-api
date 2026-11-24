# デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる。
"""Run against a fresh, migrated loopback demo database on every test."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Route
from pytest_given import scenario

from tests.support.catalog import invocation_headers
from tests.support.catalog_journey import catalog_journey
from tests.support.list_layout import visible_table_ratio
from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


@pytest.fixture
def demo_url(tmp_path: Path) -> Iterator[str]:
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "e2e.db")}
    with serve_portal(env) as url:
        yield url


@scenario("提供者の公開から承認・取消までを画面で操作する", tags=["CAT", "AUTH", "AUDIT"])
def test_user_flow(demo_url: str, request: pytest.FixtureRequest) -> None:
    """デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる"""
    catalog_journey(demo_url, request.node)


def test_home_chat_and_inquiry(demo_url: str, request: pytest.FixtureRequest) -> None:
    """ホームで商品と手順を調べ、運営への問い合わせを明示的に送信できる。"""
    import httpx
    from playwright.sync_api import expect, sync_playwright

    from packages.tools.demo.seed_marketplace import seed

    with httpx.Client(base_url=demo_url + "/api/", trust_env=False) as api:
        seed(api, 1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(demo_url)
        page.get_by_role("button", name="利用チーム", exact=True).click()
        expect(page.get_by_role("heading", name="どのAPIをお探しですか？")).to_be_visible()
        page.get_by_role("button", name="在庫を確認できるAPIを探して").click()
        history = page.get_by_role("log", name="会話")
        expect(history.locator('a[href^="#/api/"]').first).to_be_visible()
        capture_image(request.node, "chat", page, "recommendation", "日本語の質問への商品候補")
        page.get_by_label("質問", exact=True).fill("APIキーを発行する手順を教えて")
        page.get_by_role("button", name="送信", exact=True).click()
        expect(history.get_by_role("link", name="ガイドで確認").first).to_be_visible()
        page.get_by_role("button", name="運営に問い合わせる").click()
        page.get_by_label("問い合わせ内容").fill("利用申請を確認してください")
        page.get_by_role("button", name="問い合わせを送信").click()
        expect(history.get_by_text("問い合わせを受け付けました。受付番号", exact=False)).to_be_visible()
        page.get_by_role("link", name="自分の問い合わせ", exact=True).click()
        expect(page.get_by_text("回答待ち", exact=True)).to_be_visible()
        capture_image(request.node, "chat", page, "inquiry", "受付後に確認した自分の問い合わせ")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()


def test_submit_from_inquiries(demo_url: str, request: pytest.FixtureRequest) -> None:
    """利用者が問い合わせ画面から送信すると受付番号が表示され、再訪しても回答待ちの履歴を確認できる。"""
    from playwright.sync_api import expect, sync_playwright

    from tests.support.catalog_journey import navigate

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(demo_url)
        page.get_by_role("button", name="利用チーム", exact=True).click()
        navigate(page, "問い合わせ")
        question = "新しいプロジェクトの利用手順を教えてください"
        page.locator("summary").filter(has_text="新しい問い合わせ").click()
        field = page.get_by_label("問い合わせ内容")
        field.fill(question)
        page.get_by_role("button", name="問い合わせを送信").click()
        receipt = page.get_by_role("status").filter(has_text="問い合わせを受け付けました。受付番号 ")
        expect(receipt).to_be_visible()
        key = receipt.inner_text().split("受付番号 ")[1]
        ticket = page.get_by_role("row").filter(has_text=question)
        expect(ticket.get_by_role("rowheader", name=key, exact=True)).to_be_visible()
        expect(ticket.get_by_text("回答待ち")).to_be_visible()
        expect(page.locator("#inquiry-question")).to_have_value("")
        capture_image(
            request.node, "inquiries", page, "submitted", "問い合わせ画面の受付番号と回答待ちの履歴"
        )
        page.reload()
        expect(ticket.get_by_role("rowheader", name=key, exact=True)).to_be_visible()
        expect(ticket).to_have_count(1)
        browser.close()


def test_large_catalog(demo_url: str, request: pytest.FixtureRequest) -> None:
    """6業務・20拠点の公開120件を全件照合し、PC・スマートフォンの検索とページ送りを確認する"""
    import httpx
    from playwright.sync_api import expect, sync_playwright

    from packages.tools.demo.seed_marketplace import CATALOG, offer, seed
    from tests.support.catalog_journey import browser_evidence, navigate

    with httpx.Client(base_url=demo_url + "/api/", trust_env=False) as api:
        ids = seed(api, 20)
        provider = {"Authorization": "Bearer " + api.post("demo/provider").json()["access_token"]}
        consumer = {"Authorization": "Bearer " + api.post("demo/consumer").json()["access_token"]}
        draft = api.post("apis", headers=provider, json=offer(CATALOG[0], 21)).raise_for_status().json()
        observed: list[str] = []
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
                navigate(view, "APIカタログ")
                expect(view.get_by_role("heading", name="API一覧（120件）")).to_be_visible()
                expect(view.locator(".result-table tbody tr")).to_have_count(12)
                assert visible_table_ratio(view.get_by_role("table", name="API一覧")) >= 0.70
                expect(view.get_by_label("キーワードで検索")).to_be_hidden()
                assert view.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture(desktop, "catalog", "120件の公開カタログ。先頭12件を表示するデスクトップ画面")
            capture(mobile, "phone", "390px幅で同じ公開カタログを表示")
            desktop.get_by_role("button", name="次へ").click()
            expect(desktop.get_by_text("13–24 件を表示")).to_be_visible()
            desktop.get_by_role("button", name="前へ").click()
            expect(desktop.get_by_text("1–12 件を表示")).to_be_visible()
            mobile.locator("summary").filter(has_text="検索条件").click()
            mobile.get_by_label("キーワードで検索").fill("岐阜")
            mobile.get_by_label("提供環境").select_option("production")
            mobile.get_by_label("提供環境").press("Tab")
            assert mobile.get_by_role("button", name="検索", exact=True).evaluate(
                "el => el.matches(':focus-visible') && getComputedStyle(el).outlineStyle !== 'none'"
            )
            mobile.keyboard.press("Enter")
            expect(mobile.get_by_role("heading", name="API一覧（3件）")).to_be_visible()
            expect(mobile.locator(".result-table tbody tr")).to_have_count(3)
            assert all("岐阜" in name for name in mobile.locator(".asset-title").all_text_contents())
            capture(mobile, "filtered", "キーワードと本番環境で絞り、120件から目的の3件を抽出")
            mobile.locator("summary").filter(has_text="検索条件").click()
            mobile.get_by_label("キーワードで検索").fill("該当なしの検索語")
            mobile.get_by_label("キーワードで検索").press("Enter")
            expect(mobile.get_by_text("該当するAPIはありません。")).to_be_visible()
            expect(mobile.locator(".result-table tbody tr")).to_have_count(0)
            capture(mobile, "empty", "該当なしを明示し、検索条件を変更できる画面")
        browser.close()
    request.node.user_properties.append(
        (
            "finding",
            "実測値：6業務×20拠点の公開120件、未公開1件。全10ページを照合し、重複・欠落・下書き混入は各0件。390pxと1440pxで横幅内に収まり、検索ボタンをキーボードで実行できた。",
        )
    )


def test_console_visual_modes(demo_url: str, request: pytest.FixtureRequest) -> None:
    """11月の外観変更を反映した明暗テーマの文字コントラストとキーボード操作を確認する"""
    import httpx
    from playwright.sync_api import expect, sync_playwright

    from packages.tools.demo.seed_marketplace import seed
    from tests.support.catalog_journey import browser_evidence, navigate

    with httpx.Client(base_url=demo_url + "/api/", trust_env=False) as api:
        seed(api, 1)

    def contrast(locator: Locator) -> float:
        ratio: float = locator.evaluate("""element => {
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
        return ratio

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="light")
        with browser_evidence(request.node, "visual-modes", page, page) as capture:
            page.goto(demo_url)
            page.get_by_role("button", name="提供チーム", exact=True).click()
            navigate(page, "APIカタログ")
            link = page.locator(".asset-title").first
            expect(link).to_be_visible()
            page.locator("summary").filter(has_text="検索条件").click()
            primary = page.get_by_role("button", name="検索", exact=True)
            mode = page.get_by_label("表示モード")
            for theme, link_color in (("light", "rgb(37, 36, 32)"), ("dark", "rgb(239, 238, 235)")):
                mode.select_option(theme)
                expect(link).to_have_css("color", link_color)
                expect(primary).to_have_css("background-color", link_color)
                expect(page.locator("body")).to_have_css(
                    "background-color", "rgb(249, 249, 249)" if theme == "light" else "rgb(16, 15, 14)"
                )
                expect(primary).to_have_css("border-radius", "4px")
                expect(page.locator(".result-table").first).to_have_css("border-radius", "4px")
                expect(page.locator(".form-select").first).to_have_css("border-radius", "4px")
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
            expect(page.locator(".result-table tbody tr")).to_have_count(1)
            expect(link).to_contain_text("配送")
            mode.select_option("auto")
            page.emulate_media(color_scheme="dark")
            expect(link).to_have_css("color", "rgb(239, 238, 235)")
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload()
            navigate(page, "業務操作履歴")
            expect(page.locator(".result-table tbody tr").first).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture(page, "mobile-dark", "端末のダーク設定を引き継いだ390px幅の業務操作履歴")
            page.emulate_media(forced_colors="active")
            assert page.evaluate("matchMedia('(forced-colors: active)').matches")
            page.locator("summary").filter(has_text="検索条件").click()
            page.get_by_label("操作", exact=True).press("Tab")
            button = page.get_by_role("button", name="絞り込む")
            expect(button).to_be_focused()
            expect(button).to_have_css("outline-style", "solid")
            capture(page, "forced", "OSの強制カラーで表示した業務操作履歴とキーボードのフォーカス枠")
        browser.close()


def test_governance_console(demo_url: str, request: pytest.FixtureRequest) -> None:
    """3役で利用状況、ユーザー管理、名称で選んだ宛先への通知、ログ保存、掲載終了を確認する。"""
    import json
    import re

    import httpx
    from playwright.sync_api import expect, sync_playwright

    from tests.support.catalog import approved, headers
    from tests.support.catalog_journey import browser_evidence, navigate

    with httpx.Client(base_url=demo_url, trust_env=False) as api, sync_playwright() as pw:
        operator, owner, consumer = (headers(api, r) for r in ("admin", "provider", "consumer"))
        key, _, path = approved(api, owner, consumer)
        api.put(
            "/api/workspace/units/sales", headers=operator, json={"name": "営業部", "kind": "department"}
        ).raise_for_status()
        api.put(
            "/api/workspace/units/finance",
            headers=operator,
            json={"name": "受注から出荷までの納期改善", "kind": "project", "parent": "sales"},
        ).raise_for_status()
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        admin, provider, user = (
            browser.new_page(viewport={"width": 1440, "height": 960}) for _ in range(3)
        )
        for view in (admin, provider):
            view.on("dialog", lambda dialog: dialog.accept())
        with browser_evidence(request.node, "governance", provider, user) as capture:
            for view, label, role in (
                (admin, "管理者", "管理者"),
                (provider, "提供チーム", "提供者"),
                (user, "利用チーム", "利用者"),
            ):
                view.goto(demo_url)
                view.get_by_role("button", name=label, exact=True).click()
                expect(view.get_by_role("heading", name="どのAPIをお探しですか？")).to_be_visible()
                navigate(view, "利用状況")
                expect(view.get_by_text(role + "としての利用状況")).to_be_visible()

            navigate(admin, "ユーザー管理")
            admin.locator("summary").filter(has_text="ユーザーを追加").click()
            admin.get_by_label("メールアドレス").fill("catalog-reader@example.org")
            admin.get_by_label("所属プロジェクト").select_option("finance")
            admin.get_by_role("button", name="追加する").click()
            row = admin.get_by_role("row").filter(has_text="catalog-reader@example.org")
            expect(row).to_be_visible()
            capture(admin, "members", "管理者が追加した利用者と所属プロジェクト")
            row.get_by_role("button", name="削除", exact=True).click()
            expect(row).to_have_count(0)
            recipient = "営業部 / 受注から出荷までの納期改善"
            for view, label, field, option, expected in (
                (admin, "管理者からのお知らせ", "送信先", recipient, "finance"),
                (
                    provider,
                    "在庫API更新予定",
                    "送信先のAPIと利用プロジェクト",
                    f"在庫 · {recipient} · 検証",
                    f"{key}/finance/sandbox",
                ),
            ):
                view.locator(".bell-button").click()
                view.get_by_text("利用者に通知を送る").click()
                assert view.get_by_label(field, exact=True).select_option(label=option) == [expected]
                view.get_by_label("件名").fill(label)
                view.get_by_label("お知らせ本文").fill("検証環境の利用時間を変更します。")
                view.get_by_role("button", name="通知を送信", exact=True).click()
                expect(view.get_by_text("通知を送信しました")).to_be_visible()
            navigate(provider, "アラート")
            provider.locator("summary").filter(has_text="利用件数のルール").click()
            provider.get_by_label("しきい値（件）").fill("2")
            provider.get_by_label("集計期間").select_option("1440")
            provider.get_by_label("到達時の動作").select_option("stop")
            provider.get_by_role("button", name="ルールを保存").click()
            expect(provider.get_by_text("アラート設定を保存しました")).to_be_visible()
            capture(provider, "alert", "提供者が設定した検証環境の上限と停止条件")
            call = invocation_headers(api, consumer)
            assert [api.get(path, headers=call).status_code for _ in range(3)] == [200, 200, 429]
            user.locator(".bell-button").click()
            expect(user.get_by_text("利用件数アラート", exact=True)).to_be_visible()
            notice = user.get_by_role("row").filter(has_text="在庫API更新予定")
            notice.get_by_role("button", name="既読にする").click()
            expect(notice.get_by_role("cell", name="既読", exact=True)).to_be_visible()
            expect(user.get_by_text("管理者からのお知らせ", exact=True)).to_be_visible()
            capture(user, "notices", "管理者・提供者・しきい値からの通知と個人の既読状態")
            navigate(user, "メトリクス")
            user.locator("summary").filter(has_text="検索条件").click()
            user.get_by_label("表示指標").select_option("denied")
            user.get_by_label("期間", exact=True).select_option("1")
            user.get_by_label("集計間隔").select_option("5")
            user.get_by_role("button", name="条件を適用").click()
            expect(user.get_by_role("heading", name="拒否件数")).to_be_visible()
            capture(user, "metrics", "利用者の拒否件数。直近1時間を5分間隔で表示")
            user.get_by_role("button", name=re.compile(r"UTC · 1$")).click()
            denied = user.get_by_role("row").filter(has=user.get_by_role("cell", name="429", exact=True))
            expect(denied).to_contain_text("GET /items")
            capture(user, "access", "グラフから開いた同じ時間帯のアクセスログ")
            with user.expect_download() as saved:
                user.get_by_role("button", name="アクセスログをダウンロード").click()
            assert sorted(
                json.loads(line)["status"] for line in saved.value.path().read_text().splitlines()
            ) == [200, 200, 429]
            trace = denied.get_by_role("link").inner_text()
            denied.click()
            expect(user.get_by_role("table", name="呼び出しの詳細")).to_contain_text("http_429")
            navigate(user, "業務操作履歴")
            user.locator("summary").filter(has_text="検索条件").click()
            user.get_by_label("リクエストID", exact=True).fill(trace)
            user.get_by_role("button", name="絞り込む").click()
            expect(user.get_by_text("呼び出し拒否", exact=True).last).to_be_visible()
            with user.expect_download() as audit_file:
                user.get_by_role("button", name="業務監査をダウンロード").click()
            assert json.loads(audit_file.value.path().read_text())["action"] == "invoke.denied"
            capture(user, "audit", "429のリクエストIDで照合した業務監査")
            for view, role in ((admin, "管理者"), (provider, "提供者"), (user, "利用者")):
                navigate(view, "利用状況")
                expect(view.locator(".recent-call")).to_have_count(3 if role == "利用者" else 0)
                expect(
                    view.locator(".stat").filter(has_text="直近24時間の呼び出し").locator("strong")
                ).to_have_text("3")
                capture(view, "home-" + role, role + "の利用状況。直近の呼び出し3件と429の記録")
            navigate(provider, "提供するAPI")
            provider.get_by_role("link", name="在庫", exact=True).click()
            provider.get_by_role("button", name="内容を編集").click()
            provider.get_by_label("API名", exact=True).fill("棚卸・在庫照会")
            provider.get_by_role("button", name="変更を保存").click()
            expect(provider.get_by_role("heading", name="棚卸・在庫照会")).to_be_visible()
            capture(provider, "renamed", "名称を変更した商品")
            provider.get_by_role("button", name="掲載を取り下げる").click()
            expect(provider.get_by_role("button", name="公開する")).to_be_visible()
            provider.get_by_role("button", name="APIを削除").click()
            expect(provider.get_by_text("APIを削除しました")).to_be_visible()
            capture(provider, "deleted", "削除操作の結果")
            assert api.get(path, headers=call).status_code == 404
        browser.close()


def test_portal_login_on_mobile(demo_url: str, request: pytest.FixtureRequest) -> None:
    """スマートフォンでログインし、確認コードを入力して元のカタログへ戻れる。"""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        token = page.request.post(demo_url + "/api/demo/consumer").json()["access_token"]
        page.route(
            "**/api/config",
            lambda route: route.fulfill(
                json={
                    "demo": False,
                    "client_id": "portal",
                    "identity_endpoint": demo_url + "/identity",
                }
            ),
        )
        operations = []

        def identity(route: Route) -> None:
            operation = route.request.headers["x-amz-target"].split(".")[-1]
            operations.append(operation)
            if operation == "InitiateAuth":
                route.fulfill(json={"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "pending"})
            else:
                route.fulfill(json={"AuthenticationResult": {"AccessToken": token}})

        page.route("**/identity", identity)
        page.goto(demo_url + "/#/catalog")
        page.get_by_label("ユーザー名", exact=True).fill("member")
        page.get_by_label("パスワード", exact=True).fill("example-password")
        page.get_by_role("button", name="ログイン", exact=True).click()
        page.get_by_label("確認コード").fill("012345")
        page.get_by_role("button", name="確認してログイン").click()
        expect(page.get_by_role("heading", name="APIカタログ", exact=True)).to_be_visible()
        capture_image(request.node, "login", page, "signed-in", "認証後に戻ったカタログ")
        assert operations == ["InitiateAuth", "RespondToAuthChallenge"]
        page.get_by_role("button", name="ナビゲーション", exact=True).click()
        expect(page.get_by_label("すべての公開APIを検索")).to_be_visible()
        page.get_by_role("button", name="ログアウト").click()
        expect(page.get_by_role("heading", name="継手APIにログイン")).to_be_visible()
        assert page.url.startswith(demo_url + "/")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()
