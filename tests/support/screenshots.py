"""検証画面を撮影して保存する。"""

import pytest
from playwright.sync_api import Locator, Page

from tests.support.portal_server import ROOT


def capture_image(case: pytest.Item, mode: str, view: Page | Locator, name: str, caption: str) -> None:
    folder = ROOT / "artifacts" / "screenshots" / mode
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / (name + ".png")
    view.screenshot(path=path, animations="disabled")
    case.user_properties.append(
        ("screenshot", path.relative_to(ROOT / "artifacts").as_posix() + "|" + caption)
    )
