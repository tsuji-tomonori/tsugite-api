# 管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する。
"""Browser coverage for an administrator and a project leader using real portal routes."""

import os
import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect, sync_playwright

from tests.support.catalog import approved, headers
from tests.support.catalog_journey import browser_evidence
from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


def menu(page: Page, label: str | re.Pattern[str]) -> None:
    page.get_by_role("navigation", name="ポータル").get_by_role("button", name=label).click()


def open_form(page: Page, summary: str) -> None:
    label = page.locator("summary").filter(has_text=re.compile("^" + re.escape(summary) + "$"))
    # A retained PuePy details element can remain open after a successful submit.
    host = label.locator("..")
    if host.get_attribute("open") is None:
        label.click()


def test_workspace_key_console(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "org.db")}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        owner, user = (headers(api, r) for r in ("provider", "consumer"))
        asset, _, path = approved(api, owner, user)
        email = "finance.member.with.a.long.address@example.test"
        api.post(
            "/api/members",
            headers=headers(api, "admin"),
            json={"full_name": "試験 花子", "email": email, "project": "finance", "role": "consumer"},
        ).raise_for_status()
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        admin, leader = (browser.new_page(viewport={"width": 1440, "height": 960}) for _ in range(2))
        for page in (admin, leader):
            page.on("dialog", lambda dialog: dialog.accept())
        with browser_evidence(request.node, "workspace", admin, leader) as capture:
            admin.goto(url)
            admin.get_by_role("button", name="管理者", exact=True).click()
            expect(admin.get_by_role("heading", name="どのAPIをお探しですか？")).to_be_visible()
            for name, identifier, parent, kind in (
                ("事業本部", "business", "", "department"),
                ("経理部", "accounts", "business", "department"),
                ("決算チーム", "closing", "accounts", "department"),
                ("会計分析", "accounting-data", "closing", "project"),
                ("監査室", "audit-office", "", "department"),
            ):
                label = "部署" if kind == "department" else "プロジェクト"
                menu(admin, label)
                admin.get_by_role("link", name=label + "を作成").click()
                admin.get_by_label("名称", exact=True).fill(name)
                admin.get_by_label("識別子", exact=True).fill(identifier)
                admin.get_by_label("親部署").select_option(parent)
                admin.get_by_role("button", name="保存", exact=True).click()
                expect(admin.get_by_role("heading", name=re.compile(name + "$"))).to_be_visible()

            admin.get_by_role("link", name="部署を編集").click()
            expect(admin.get_by_role("heading", name="部署の編集")).to_be_visible()
            admin.set_viewport_size({"width": 390, "height": 844})
            save = admin.get_by_role("button", name="保存", exact=True)
            expect(save).to_have_css("min-height", "48px")
            expect(save).to_have_css("padding-left", "24px")
            expect(save.locator("..")).to_have_css("gap", "16px")
            assert admin.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            capture(admin, "edit-mobile", "スマートフォン幅で対象の部署と保存・キャンセルの間隔を確認")
            admin.set_viewport_size({"width": 1440, "height": 960})
            admin.get_by_label("名称", exact=True).fill("内部監査室")
            admin.get_by_role("button", name="保存", exact=True).click()
            expect(admin.get_by_role("heading", name="内部監査室")).to_be_visible()
            for unit, title in (("business", "本部長"), ("audit-office", "兼務"), ("finance", "課長")):
                menu(admin, "プロジェクト" if unit == "finance" else "部署")
                admin.locator(f'a[href$="/detail/{unit}"]').click()
                members = admin.get_by_role("table", name="直接の所属メンバー")
                membership = members.get_by_role("row").filter(has_text="consumer")
                if unit == "finance":
                    invited = members.get_by_role("row").filter(has_text=email)
                    for role, label in (("link", "所属を編集"), ("button", "所属を解除")):
                        existing_action = membership.get_by_role(role, name=label).bounding_box()
                        invited_action = invited.get_by_role(role, name=label).bounding_box()
                        assert existing_action and invited_action
                        assert existing_action["x"] == invited_action["x"]
                    capture(
                        admin,
                        "direct-members",
                        "氏名とメールアドレスの長さが違う行で、所属の操作位置を確認",
                    )
                    admin.set_viewport_size({"width": 390, "height": 844})
                    assert admin.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    with admin.expect_response(
                        lambda r: "/workspace/memberships?" in r.url and r.request.method == "DELETE"
                    ) as removed:
                        invited.get_by_role("button", name="所属を解除").click()
                    assert removed.value.ok
                    expect(invited).to_have_count(0)
                    admin.set_viewport_size({"width": 1440, "height": 960})
                    membership.get_by_role("link", name="所属を編集").click()
                else:
                    admin.get_by_role("link", name="メンバーを追加").click()
                    admin.get_by_label("ユーザー", exact=True).select_option("consumer")
                admin.get_by_label("役職", exact=True).fill(title)
                admin.get_by_label("管理権限").select_option("yes")
                with admin.expect_response(
                    lambda r: r.url.endswith("/workspace/memberships") and r.request.method == "PUT"
                ) as saved:
                    admin.get_by_role("button", name="所属を保存").click()
                assert saved.value.ok
                expect(membership.get_by_text("リーダー")).to_be_visible()
                expect(membership.get_by_text(title)).to_be_visible()
                expect(admin.get_by_text("所属と役職を保存しました")).to_be_visible()

            menu(admin, "プロジェクト")
            admin.get_by_role("link", name="会計分析", exact=True).click()
            tree_end = admin.get_by_role("heading", name="事業本部 / 経理部 / 決算チーム / 会計分析")
            tree_end.scroll_into_view_if_needed()
            capture(admin, "hierarchy", "事業本部・経理部・決算チームの下に新規プロジェクトを配置")
            leader.goto(url)
            leader.get_by_role("button", name="利用チーム", exact=True).click()
            expect(leader.get_by_role("heading", name="どのAPIをお探しですか？")).to_be_visible()
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
                expect(leader.get_by_role("rowheader", name=name, exact=True)).to_be_visible()

            capture(leader, "keys", "同じプロジェクトの本人専用キーと共有キー。範囲と状態を確認")
            records = api.get("/api/keys", headers=user).raise_for_status().json()
            owned = next(k for k in records if k["name"] == "在庫試験用")
            assert owned["api_ids"] == [asset]
            call_headers = {**user, "X-Tsugite-Key-Id": owned["id"]}
            assert api.get(path, headers=call_headers).status_code == 200

            menu(leader, "部署")
            leader.get_by_role("link", name="事業本部", exact=True).click()
            leader.get_by_role("link", name="モニタリング").click()
            expect(leader.get_by_role("heading", name="部署のモニタリング")).to_be_visible()
            expect(leader.get_by_role("meter").first).to_have_attribute("value", "1")
            capture(leader, "usage", "本部リーダーがプロジェクト別・API別の利用件数を確認")
            leader.get_by_role("link", name="詳細に戻る").click()
            leader.get_by_role("button", name="利用を停止").click()
            expect(leader.get_by_role("button", name="利用を再開")).to_be_visible()
            menu(leader, "部署")
            child = leader.get_by_role("row").filter(
                has=leader.get_by_role("link", name="経理部", exact=True)
            )
            expect(child.get_by_text("事業本部の設定により利用停止中")).to_be_visible()
            capture(leader, "stopped", "上位部署の利用停止が配下の経理部に反映された状態")
            assert api.get(path, headers=call_headers).status_code in (403, 423)
            leader.get_by_role("link", name="事業本部", exact=True).click()
            leader.get_by_role("button", name="利用を再開").click()
            expect(leader.get_by_role("button", name="利用を停止")).to_be_visible()
            assert api.get(path, headers=call_headers).status_code == 200
            menu(leader, re.compile("APIキー"))
            row = leader.get_by_role("row").filter(
                has=leader.get_by_role("rowheader", name="在庫試験用")
            )
            row.get_by_role("button", name="キーを失効").click()
            expect(row.get_by_text(re.compile("失効済み"))).to_be_visible()
            assert api.get(path, headers=call_headers).status_code in (401, 403)

            for i in range(11):
                api.put(
                    f"/api/workspace/units/page-check-{i}",
                    headers=headers(api, "admin"),
                    json={"kind": "department", "name": f"一覧確認{i:02}"},
                ).raise_for_status()
            menu(admin, "部署")
            directory = admin.get_by_role("table", name="部署一覧")
            names = directory.locator("tbody th a")
            expect(names).to_have_count(10)
            first_page = names.all_text_contents()
            capture(admin, "directory", "部署一覧に10件とページ移動を表示")
            admin.get_by_role("link", name="次へ", exact=True).click()
            expect(admin).to_have_url(re.compile(r"#/departments/page/2$"))
            expect(admin.get_by_role("link", name="前へ")).to_be_visible()
            second_page = names.all_text_contents()
            assert second_page and set(first_page).isdisjoint(second_page)
            admin.go_back()
            expect(names).to_have_count(10)
            assert names.all_text_contents() == first_page
        browser.close()


def test_consumer_project_directory(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """finance の利用者には所属先が1件だけ表示され、未所属の詳細URLを開いても情報は表示されない"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "org.db")}
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.goto(url)
        page.get_by_role("button", name="利用チーム", exact=True).click()
        expect(page.get_by_role("heading", name="どのAPIをお探しですか？")).to_be_visible()
        menu(page, "プロジェクト")
        projects = page.get_by_role("table", name="プロジェクト一覧")
        expect(projects.locator("tbody tr")).to_have_count(1)
        own = projects.get_by_role("link", name="finance", exact=True)
        expect(own).to_be_visible()
        capture_image(
            request.node, "workspace", page, "own-projects", "finance だけに所属する利用者の一覧"
        )
        own.click()
        expect(page.get_by_role("heading", name="finance", exact=True)).to_be_visible()
        page.goto(url + "/#/projects/detail/supply")
        expect(page.get_by_text("対象が見つかりません。", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="supply", exact=True)).to_have_count(0)
        browser.close()


def test_retire_workspace_units(tmp_path: Path) -> None:
    """管理画面で部署を移管して子部署を引き継ぎ、未使用の子部署を削除できる。"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "retire.db")}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        admin = headers(api, "admin")
        for key, parent in (("old", ""), ("new", ""), ("child", "old")):
            api.put(
                "/api/workspace/units/" + key,
                headers=admin,
                json={"name": key, "kind": "department", "parent": parent},
            ).raise_for_status()
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(url)
        page.get_by_role("button", name="管理者", exact=True).click()
        menu(page, "部署")
        page.get_by_role("link", name="old", exact=True).click()
        open_form(page, "移管・削除")
        page.get_by_label("移管先", exact=True).select_option("new")
        page.get_by_role("button", name="部署を移管", exact=True).click()
        expect(page.get_by_role("heading", name="new", exact=True)).to_be_visible()
        menu(page, "部署")
        page.get_by_role("link", name="child", exact=True).click()
        expect(page.get_by_role("heading", name="new / child", exact=True)).to_be_visible()
        open_form(page, "移管・削除")
        page.get_by_role("button", name="部署を削除", exact=True).click()
        expect(page.get_by_role("table", name="部署一覧")).to_be_visible()
        expect(page.get_by_role("link", name="child", exact=True)).to_have_count(0)
        browser.close()
