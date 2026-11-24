# カタログと提供一覧の商品を表示する。
from __future__ import annotations

from actions.catalog import search, turn_page
from content.portal_labels import LABEL
from puepy import t
from runtime.portal_ui import action, ctx, route

from components.controls import btn, field


def cards() -> None:
    """商品一覧と検索・ページ移動を表示する。"""
    count, page, size = ctx["total"], ctx["page"], ctx["size"]
    start = (page - 1) * size + 1 if count else 0
    pages = max(1, (count + size - 1) // size)
    with t.div(classes="collection-tools"):
        with t.div(classes="results-head"):
            t.h2(f"API一覧（{count}件）")
            t.span(f"{start}–{min(count, page * size)} 件を表示", classes="muted")
        with t.form(classes="searchbar", on_submit=action(search)):
            field(
                "キーワードで検索",
                "search",
                text=ctx["query"],
                placeholder="API名、用途、提供元、操作名",
            )
            field(
                "提供環境",
                "filter-env",
                options=[
                    ("", "すべての環境"),
                    ("sandbox", "検証"),
                    ("staging", "準本番"),
                    ("production", "本番"),
                ],
                text=ctx["env"],
            )
            t.button("検索", type="submit", classes="btn btn-primary")
    if not count:
        with t.div(classes="empty"):
            t.h3("該当するAPIはありません。")
            t.p("キーワードや提供環境を変更して検索してください。")
    with t.div(classes="card-grid"):
        for row in ctx["rows"]:
            with t.article(classes="asset-card"):
                with t.h3():
                    t.a(row["name"], href="#/api/" + row["id"], classes="asset-title")
                t.p(row["summary"], classes="description")
                with t.div(classes="card-foot"):
                    with t.div():
                        t.strong("提供元", classes="key")
                        t.span(row["owner"], classes="owner")
                    with t.div():
                        t.strong("提供環境", classes="key")
                        with t.div(classes="pills"):
                            for env in row["environments"]:
                                t.span(LABEL[env], classes="pill " + env)
                            if not row["published"]:
                                t.span("下書き", classes="pill pending")
                    if route() == "inventory" and row["published"]:
                        t.span("公開中", classes="pill approved")
    if pages > 1:
        with t.div(classes="pager"):
            if page > 1:
                btn("前へ", turn_page, page - 1)
            t.span(f"{page} / {pages} ページ")
            if page < pages:
                btn("次へ", turn_page, page + 1)
