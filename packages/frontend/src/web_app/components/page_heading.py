"""画面名と補足説明、画面に対する操作を共通の位置に描画する。"""

from collections.abc import Callable

from puepy import t


def page_heading(title: str, description: str = "", action: Callable[[], object] | None = None) -> None:
    """画面名を主見出しにし、指定された補足説明と操作を添える。"""
    with t.div(classes="page-heading"):
        with t.div():
            t.h1(title)
            if description:
                t.p(description, classes="subtitle")
        if action:
            action()
