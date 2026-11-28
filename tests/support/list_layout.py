"""一覧画面のレイアウトを検証する。"""

from playwright.sync_api import Locator


def visible_table_ratio(table: Locator) -> float:
    """画面高に対して、実際に表示されている表の高さが占める割合を返す。"""
    return float(
        table.evaluate("""el => {
        const bounds = el.getBoundingClientRect();
        if (bounds.top < 0) return 0;
        const visible = Math.min(innerHeight, bounds.bottom) - Math.max(0, bounds.top);
        return Math.max(0, visible) / innerHeight;
    }""")
    )
