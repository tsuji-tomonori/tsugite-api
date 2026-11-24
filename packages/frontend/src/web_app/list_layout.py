"""一覧の検索条件と結果表で共通の表示。"""

from contextlib import contextmanager

from puepy import t


@contextmanager
def disclosure(title, *, status="", expanded=False):
    with t.details(classes="list-disclosure", open=expanded):
        with t.summary():
            t.span(title)
            if status:
                t.small(status, classes="muted")
        with t.div(classes="disclosure-body"):
            yield


@contextmanager
def result_table(label, headings, *, body_id=None):
    with t.div(classes="resource-table result-table", tabindex="0", role="region", aria_label=label):
        with t.table(aria_label=label):
            with t.thead(), t.tr():
                for heading in headings:
                    t.th(heading, scope="col")
            with t.tbody(**({"id": body_id} if body_id else {})):
                yield


def download_button(label, on_click):
    with t.button(
        type="button",
        classes="btn btn-outline-secondary",
        aria_label=label + "して保存",
        title=label,
        on_click=on_click,
    ):
        t.span("ダウンロード", classes="download-label")
        t.span("保存", classes="download-short")
