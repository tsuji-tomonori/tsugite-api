# 管理者が属性を設定し、利用者の画面で確認できることを検証する。
"""任意属性の設定と本人の画面を、独立したセッションで確認する。"""

import os

from playwright.sync_api import expect, sync_playwright

from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


def test_metadata_assignment_console(tmp_path, request):
    """雇用区分を登録して利用者に割り当てると本人のプロフィールに値が表示される。"""
    env = {
        **os.environ,
        "TSUGITE_DEMO": "1",
        "DATABASE_URL": "sqlite:///" + str(tmp_path / "metadata.db"),
    }
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        admin = browser.new_page()
        admin.goto(url)
        admin.get_by_role("button", name="管理者", exact=True).click()
        admin.get_by_role("button", name="属性一覧", exact=True).click()
        fields = admin.get_by_role("table", name="メタデータ項目")
        expect(fields.get_by_text("使用中", exact=True)).to_have_count(2)
        admin.get_by_role("link", name="項目を追加").click()
        admin.get_by_label("項目名").fill("雇用区分")
        admin.get_by_label("キー", exact=False).fill("employment")
        admin.get_by_role("button", name="保存", exact=True).click()
        expect(fields.get_by_role("link", name="雇用区分")).to_be_visible()
        admin.get_by_role("navigation", name="ポータル").get_by_role(
            "button", name="雇用区分", exact=True
        ).click()
        admin.get_by_role("link", name="値を追加").click()
        admin.get_by_label("名称", exact=True).fill("業務委託")
        admin.get_by_label("識別子", exact=True).fill("contractor")
        admin.get_by_role("button", name="保存", exact=True).click()
        admin.get_by_role("link", name="メンバーを追加").click()
        admin.get_by_label("ユーザー", exact=True).select_option("consumer")
        admin.get_by_role("button", name="所属を保存").click()
        expect(admin.get_by_role("table", name="直接の所属メンバー")).to_contain_text("consumer")
        user = browser.new_page()
        user.goto(url)
        user.get_by_role("button", name="利用チーム", exact=True).click()
        user.get_by_role("button", name="自分のプロフィール", exact=True).click()
        profile = user.get_by_role("table", name="利用者のメタデータ")
        expect(profile.get_by_role("row").filter(has_text="雇用区分")).to_contain_text("業務委託")
        expect(profile.get_by_role("row").filter(has_text="プロジェクト")).to_contain_text("finance")
        capture_image(
            request.node, "metadata", profile, "user-metadata", "本人の雇用区分とプロジェクトを確認"
        )
        user.get_by_role("button", name="属性一覧", exact=True).click()
        expect(user.get_by_role("link", name="項目を追加")).to_have_count(0)
        browser.close()
