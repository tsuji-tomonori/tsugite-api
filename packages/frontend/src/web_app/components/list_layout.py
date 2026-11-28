"""一覧の検索条件と結果表に共通する部品を描画する。"""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from puepy import t


@contextmanager
def disclosure(title: str, *, status: str = "", expanded: bool = False) -> Iterator[None]:
    """条件を折りたためる入力欄を描画する。"""
    with t.details(classes="list-disclosure", open=expanded):
        with t.summary():
            t.span(title)
            if status:
                t.small(status, classes="muted")
        with t.div(classes="disclosure-body"):
            yield


@contextmanager
def result_table(label: str, headings: Sequence[str], *, body_id: str | None = None) -> Iterator[None]:
    """一覧に共通の列見出しと表本体を描画する。"""
    with t.div(classes="resource-table result-table", tabindex="0", role="region", aria_label=label):
        with t.table(aria_label=label):
            with t.thead(), t.tr():
                for heading in headings:
                    t.th(heading, scope="col")
            with t.tbody(**({"id": body_id} if body_id else {})):
                yield


def download_button(label: str, on_click: Callable[..., Any]) -> None:
    """画面幅に合わせた保存ボタンを描画する。"""
    with t.button(
        type="button",
        classes="btn btn-outline-secondary",
        aria_label=label + "して保存",
        title=label,
        on_click=on_click,
    ):
        t.span("ダウンロード", classes="download-label")
        t.span("保存", classes="download-short")
