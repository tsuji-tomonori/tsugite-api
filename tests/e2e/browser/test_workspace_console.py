"""Browser coverage for an administrator and a project leader using real portal routes."""

import os
import re

import httpx
from playwright.sync_api import expect, sync_playwright

from tests.support.catalog import approved, headers
from tests.support.catalog_journey import browser_evidence
from tests.support.portal_server import serve_portal


def menu(page, label):
    page.get_by_role("navigation", name="ポータル").get_by_role("button", name=label).click()


def open_form(page, summary):
    label = page.locator("summary").filter(has_text=re.compile("^" + re.escape(summary) + "$"))
    # A retained PuePy details element can remain open after a successful submit.
    host = label.locator("..")
    if host.get_attribute("open") is None:
        label.click()


def test_workspace_key_console(tmp_path, request):
    """管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "org.db")}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        owner, user = (headers(api, r) for r in ("provider", "consumer"))
        asset, _, path = approved(api, owner, user)
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        admin, leader = (browser.new_page(viewport={"width": 1440, "height": 960}) for _ in range(2))
        for page in (admin, leader):
            page.on("dialog", lambda dialog: dialog.accept())
        with browser_evidence(request.node, "workspace", admin, leader) as capture:
            admin.goto(url)
            admin.get_by_role("button", name="管理者", exact=True).click()
            expect(admin.get_by_text("管理者としての利用状況")).to_be_visible()
            menu(admin, re.compile("組織|部署"))
            for name, identifier, parent, kind in (
                ("事業本部", "business", "", "department"),
                ("経理部", "accounts", "business", "department"),
                ("決算チーム", "closing", "accounts", "department"),
                ("会計分析", "accounting-data", "closing", "project"),
                ("監査室", "audit-office", "", "department"),
            ):
                open_form(admin, "部署・プロジェクトの登録と編集")
                admin.get_by_label("名称", exact=True).fill(name)
                admin.get_by_label("識別子", exact=True).fill(identifier)
                admin.get_by_label("種類", exact=True).select_option(kind)
                admin.get_by_label("親部署").select_option(parent)
                admin.get_by_role("button", name="組織設定を保存").click()
                expect(admin.get_by_role("heading", name=re.compile(name + "$"))).to_be_visible()

            for unit, title in (("business", "本部長"), ("audit-office", "兼務"), ("finance", "課長")):
                open_form(admin, "所属・役職・リーダーを設定")
                admin.get_by_label("ユーザー", exact=True).select_option("consumer")
                admin.get_by_label("所属先").select_option(unit)
                admin.get_by_label("役職", exact=True).fill(title)
                admin.get_by_label("管理権限").select_option("yes")
                with admin.expect_response(
                    lambda r: r.url.endswith("/workspace/memberships") and r.request.method == "PUT"
                ) as saved:
                    admin.get_by_role("button", name="所属を保存").click()
                assert saved.value.ok
                membership = admin.locator(".compact-row span").filter(
                    has_text=f"consumer · {unit} · {title}"
                )
                expect(membership).to_have_count(1)
                expect(admin.get_by_text("所属と役職を保存しました")).to_be_visible()

            tree_end = admin.get_by_role("heading", name="事業本部 / 経理部 / 決算チーム / 会計分析")
            tree_end.scroll_into_view_if_needed()
            capture(admin, "hierarchy", "事業本部・経理部・決算チームの下に新規プロジェクトを配置")
            leader.goto(url)
            leader.get_by_role("button", name="利用チーム", exact=True).click()
            expect(leader.get_by_text("利用者としての利用状況")).to_be_visible()
            menu(leader, re.compile("APIキー"))
            for name, kind, scope in (
                ("在庫試験用", "personal", "selected"),
                ("経理共有", "shared", "all"),
            ):
                open_form(leader, "APIキーを作成")
                leader.get_by_label("キー名", exact=True).fill(name)
                leader.get_by_label("プロジェクト", exact=True).select_option("finance")
                leader.get_by_label("キーの種類").select_option(kind)
                leader.get_by_label("APIの範囲").select_option(scope)
                if scope == "selected":
                    open_form(leader, "対象APIを選ぶ")
                    leader.get_by_label("在庫", exact=True).check()
                leader.get_by_role("button", name="キーを発行").click()
                expect(leader.locator("#issued-secret")).to_be_visible()
                # Never capture or retain a newly issued credential in test artifacts.
                try:
                    assert len(leader.locator("#issued-secret").inner_text()) >= 24
                finally:
                    leader.get_by_role("button", name="表示を閉じる").click()
                    expect(leader.locator("#issued-secret")).to_have_count(0)
                expect(leader.get_by_role("heading", name=name, exact=True)).to_be_visible()

            capture(leader, "keys", "同じプロジェクトの本人専用キーと共有キー。範囲と状態を確認")
            records = api.get("/api/keys", headers=user).raise_for_status().json()
            owned = next(k for k in records if k["name"] == "在庫試験用")
            assert owned["api_ids"] == [asset]
            call_headers = {**user, "X-Tsugite-Key-Id": owned["id"]}
            assert api.get(path, headers=call_headers).status_code == 200

            menu(leader, re.compile("組織|部署"))
            root = leader.locator("article").filter(
                has=leader.get_by_role("heading", name="事業本部", exact=True)
            )
            root.get_by_role("button", name="メンバーと利用状況").click()
            expect(root.get_by_role("heading", name="利用状況")).to_be_visible()
            expect(root.get_by_text(re.compile("呼び出し 1 件"))).to_be_visible()
            capture(leader, "usage", "本部リーダーが所属メンバーとAPI別の利用件数を確認")
            root.get_by_role("button", name="利用を停止").click()
            expect(root.get_by_role("button", name="利用を再開")).to_be_visible()
            child = leader.locator("article").filter(
                has=leader.get_by_role("heading", name="事業本部 / 経理部", exact=True)
            )
            expect(child.get_by_text(re.compile("事業本部の設定により利用停止中"))).to_be_visible()
            assert api.get(path, headers=call_headers).status_code in (403, 423)
            root.get_by_role("button", name="利用を再開").click()
            expect(root.get_by_role("button", name="利用を停止")).to_be_visible()
            assert api.get(path, headers=call_headers).status_code == 200
            menu(leader, re.compile("APIキー"))
            row = leader.locator("article").filter(has=leader.get_by_role("heading", name="在庫試験用"))
            row.get_by_role("button", name="キーを失効").click()
            expect(row.get_by_text(re.compile("失効済み"))).to_be_visible()
            assert api.get(path, headers=call_headers).status_code in (401, 403)
        browser.close()
