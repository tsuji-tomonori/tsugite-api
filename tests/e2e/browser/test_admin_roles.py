"""名簿から個人の管理者権限を付与・剥奪する。"""

import os

from playwright.sync_api import expect, sync_playwright

from tests.e2e.browser.test_workspace_console import menu
from tests.support.portal_server import serve_portal
from tests.support.screenshots import capture_image


def test_manage_admin_role(tmp_path, request):
    """ユーザー管理で別の管理者を追加し、権限の表示を確認してから剥奪できる。"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "roles.db")}
    with serve_portal(env) as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(url)
        page.get_by_role("button", name="管理者", exact=True).click()
        menu(page, "ユーザー管理")
        row = page.get_by_role("row").filter(has=page.get_by_role("rowheader", name="provider"))
        row.get_by_role("button", name="管理者権限を付与").click()
        expect(row.get_by_role("cell", name="あり", exact=True)).to_be_visible()
        capture_image(
            request.node, "admin-roles", page, "multiple-admins", "二人の管理者に権限ありと表示"
        )
        row.get_by_role("button", name="管理者権限を剥奪").click()
        expect(row.get_by_role("cell", name="なし", exact=True)).to_be_visible()
        browser.close()
