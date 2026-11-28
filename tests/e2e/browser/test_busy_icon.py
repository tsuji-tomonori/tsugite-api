"""待機中だけボタンの文字と同じ色のアイコンが表示されることを確認する。"""

import os

from playwright.sync_api import sync_playwright

from tests.support.portal_server import ROOT


def test_busy_icon_follows_button_color() -> None:
    """通常・主要ボタンは各配色で待機中だけ文字と同色のアイコンを表示する。"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.set_content(
            '<button class="btn">検索</button><button class="btn btn-primary">保存</button>'
        )
        page.add_style_tag(path=ROOT / "packages/frontend/public/ui.css")
        for mode, forced in (("light", "none"), ("dark", "none"), ("light", "active")):
            page.evaluate("mode => document.documentElement.style.colorScheme = mode", mode)
            page.emulate_media(forced_colors=forced)
            for button in page.get_by_role("button").all():
                button.evaluate("el => el.setAttribute('aria-busy', 'true')")
                assert button.evaluate("""el => {
                    const icon = getComputedStyle(el, '::after');
                    return icon.content === '""' && icon.maskImage !== 'none'
                        && parseFloat(icon.width) > 0 && parseFloat(icon.height) > 0
                        && icon.backgroundColor === getComputedStyle(el).color;
                }""")
                button.evaluate("el => el.removeAttribute('aria-busy')")
                assert button.evaluate("el => getComputedStyle(el, '::after').content") == "none"
        browser.close()
