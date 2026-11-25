# 管理者が招待時に氏名を入力し、本人の表示名とともに兼務先に表示して監査を確認する。
"""Browser verification for editing and reading a member profile."""

import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.browser.test_workspace_console import menu
from tests.support.catalog import headers
from tests.support.catalog_journey import browser_evidence
from tests.support.portal_server import serve_portal


def test_member_profile_management(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """管理者が招待時に氏名を入力し、本人の表示名とともに兼務先に表示して監査を確認する。"""
    email = "profile-browser@example.test"
    env = {
        **os.environ,
        "TSUGITE_DEMO": "1",
        "DATABASE_URL": "sqlite:///" + str(tmp_path / "profile.db"),
    }
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        admin, user = (browser.new_page(viewport={"width": 1440, "height": 960}) for _ in range(2))
        with browser_evidence(request.node, "member-profile", admin, user) as capture:
            admin.goto(url)
            admin.get_by_role("button", name="管理者", exact=True).click()
            menu(admin, "ユーザー管理")
            admin.locator("summary").filter(has_text="ユーザーを追加").click()
            admin.get_by_label("メールアドレス", exact=True).fill(email)
            admin.get_by_label("氏名（任意）", exact=True).fill("高橋 美咲")
            admin.get_by_label("所属プロジェクト").select_option("finance")
            admin.get_by_role("button", name="追加する", exact=True).click()
            row = admin.get_by_role("row").filter(has_text=email)
            expect(row.get_by_text("高橋 美咲")).to_be_visible()

            authorization = headers(api, "admin")
            subject = next(
                item["subject"]
                for item in api.get("/api/members", headers=authorization)
                .raise_for_status()
                .json()["items"]
                if item["email"] == email
            )
            department = "accounting"
            api.put(
                f"/api/workspace/units/{department}",
                headers=authorization,
                json={"name": "経理部", "kind": "department"},
            ).raise_for_status()
            api.put(
                "/api/workspace/memberships",
                headers=authorization,
                json={"subject": subject, "unit_id": department},
            ).raise_for_status()

            user.goto(url)
            user.get_by_text("追加したユーザーでログイン", exact=True).click()
            user.get_by_label("登録メールアドレス").fill(email)
            user.get_by_role("button", name="このユーザーでログイン").click()
            menu(user, "自分のプロフィール")
            expect(user.get_by_label("氏名（任意）")).to_have_value("高橋 美咲")
            user.get_by_label("表示名（任意）").fill("みさき")
            user.get_by_role("button", name="保存する", exact=True).click()
            expect(user.get_by_text("プロフィールを保存しました", exact=True)).to_be_visible()
            for label, key in (("プロジェクト", "finance"), ("部署", department)):
                menu(admin, label)
                admin.locator(f'a[href$="/detail/{key}"]').click()
                member = (
                    admin.get_by_role("table", name="直接の所属メンバー")
                    .get_by_role("row")
                    .filter(has_text=email)
                )
                expect(member.get_by_role("cell").nth(0)).to_have_text(email)
                expect(member.get_by_role("cell").nth(1).get_by_text("高橋 美咲")).to_be_visible()
                expect(member.get_by_role("cell").nth(1).get_by_text("みさき")).to_be_visible()
            capture(admin, "directory-names", "兼務先でメールアドレスと氏名・表示名を確認")

            menu(admin, "ユーザー管理")
            row.get_by_role("button", name="プロフィールを編集").click()
            display_name = admin.get_by_label("表示名（任意）", exact=True)
            expect(display_name).to_have_value("みさき")
            display_name.press("ControlOrMeta+a")
            display_name.press("Backspace")
            expect(display_name).to_have_value("")
            with admin.expect_response(
                lambda r: (
                    r.request.method == "PATCH" and r.url.endswith(f"/api/members/{subject}/profile")
                )
            ) as edited:
                admin.get_by_role("button", name="保存する", exact=True).click()
            saved = edited.value
            assert saved.ok and saved.json()["display_name"] is None and saved.json()["revision"] == 3
            expect(admin.get_by_text("プロフィールを保存しました", exact=True)).to_be_visible()
            menu(admin, "業務操作履歴")
            admin.locator("summary").filter(has_text="検索条件").click()
            admin.get_by_label("リクエストID", exact=True).fill(saved.headers["x-request-id"])
            admin.get_by_label("操作", exact=True).select_option("profile.admin_update")
            admin.get_by_role("button", name="絞り込む").click()
            entry = admin.get_by_role("row").filter(has_text="管理者によるプロフィール変更")
            expect(entry.get_by_text(f"対象利用者 {subject}")).to_be_visible()
        browser.close()
