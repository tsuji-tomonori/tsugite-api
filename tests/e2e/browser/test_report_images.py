import os
from pathlib import Path
from xml.etree import ElementTree

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.screenshots import capture_image
from tools import test_report


def test_report_image_viewer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """実行レポートの画像をオフラインで拡大し、キーボード・タッチ・印刷でも確認できる"""
    monkeypatch.setattr(test_report, "OUT", tmp_path)
    shots = tmp_path / "screenshots"
    shots.mkdir()
    suite = ElementTree.Element("testsuite")
    case = ElementTree.SubElement(suite, "testcase", name="操作画面")
    properties = ElementTree.SubElement(case, "properties")
    for title in ("申請一覧", "利用履歴"):
        ElementTree.SubElement(
            properties, "property", name="screenshot", value=f"screenshots/example.png|{title}"
        )
    ElementTree.ElementTree(suite).write(tmp_path / "junit.xml", encoding="utf-8")
    (tmp_path / "aws-emulator.xml").write_text("<testsuite/>")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        reference = browser.new_page(viewport={"width": 1000, "height": 600})
        reference.set_content("<h1>記録した画面</h1>")
        reference.screenshot(path=shots / "example.png")
        reference.close()
        assert test_report.build()
        context = browser.new_context(
            offline=True, has_touch=True, viewport={"width": 390, "height": 844}
        )
        page = context.new_page()
        page.goto((tmp_path / "test-report.html").as_uri())
        page.locator("#screens summary").click()
        first = page.get_by_role("button", name="申請一覧を拡大")
        first.focus()
        page.keyboard.press("Enter")
        modal = page.get_by_role("dialog", name="申請一覧")
        expect(modal).to_be_visible()
        expect(page.get_by_role("button", name="閉じる")).to_be_focused()
        stage = modal.get_by_role("region", name="拡大画像")
        expect(stage.get_by_role("img", name="申請一覧")).to_be_visible()
        assert stage.evaluate("el => el.scrollWidth === el.clientWidth")
        capture_image(request.node, "reports", page, "viewer", "実行レポートで開いた画面証跡")
        modal.get_by_label("表示倍率").select_option("2")
        expect(stage.locator("img")).to_have_css("width", "2000px")
        stage.evaluate("el => el.scrollLeft = 350")
        assert stage.evaluate("el => el.scrollLeft") == 350
        page.keyboard.press("Escape")
        expect(modal).to_be_hidden()
        expect(first).to_be_focused()

        second = page.get_by_role("button", name="利用履歴を拡大")
        second.tap()
        modal = page.get_by_role("dialog", name="利用履歴")
        expect(modal.get_by_label("表示倍率")).to_have_value("fit")
        modal.get_by_label("表示倍率").select_option("1")
        expect(modal.locator("img")).to_have_css("width", "1000px")
        modal.get_by_role("button", name="閉じる").tap()
        expect(second).to_be_focused()

        page.locator("#screens summary").click()
        assert not page.locator("#screens details").evaluate("el => el.open")
        pdf = page.pdf()
        assert b"/Subtype /Image" in pdf
        assert not page.locator("#screens details").evaluate("el => el.open")
        browser.close()
