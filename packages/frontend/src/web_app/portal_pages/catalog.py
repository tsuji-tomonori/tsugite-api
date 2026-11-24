# APIカタログ・提供するAPIの画面と操作を定義する。
from urllib.parse import urlencode

import client
from list_layout import disclosure, result_table
from portal_labels import LABEL
from portal_navigation import go, load
from portal_ui import action, btn, ctx, field, route, value
from puepy import t
from screen_registry import Screen


async def search():
    ctx.update(query=value("search"), env=value("filter-env"), page=1)
    await load()


async def turn_page(n):
    ctx["page"] = n
    await load()


def catalog_view():
    count, page, size = ctx["total"], ctx["page"], ctx["size"]
    start = (page - 1) * size + 1 if count else 0
    pages = max(1, (count + size - 1) // size)
    inventory = route() == "inventory"
    with t.div(classes="list-tools"):
        with t.div(classes="list-count"):
            t.h2(f"API一覧（{count}件）")
        with disclosure("検索条件", status="絞り込み中" if ctx["query"] or ctx["env"] else ""):
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
        return
    headings = ["API名", "用途", "提供元", "提供環境"]
    if inventory:
        headings.append("公開状態")
    with result_table("API一覧", headings):
        for row in ctx["rows"]:
            with t.tr():
                with t.th(scope="row"):
                    t.a(row["name"], href="#/api/" + row["id"], classes="asset-title")
                t.td(row["summary"], classes="description")
                t.td(row["owner"])
                t.td("、".join(LABEL[env] for env in row["environments"]) or "—")
                if inventory:
                    t.td("公開中" if row["published"] else "下書き")
    if pages > 1:
        with t.div(classes="pager"):
            if page > 1:
                btn("前へ", turn_page, page - 1)
            t.span(f"{start}–{min(count, page * size)} 件を表示")
            t.span(f"{page} / {pages} ページ")
            if page < pages:
                btn("次へ", turn_page, page + 1)


async def load_catalog(page):
    params = {"inventory": str(page == "inventory").lower(), "page": ctx["page"], "q": ctx["query"]}
    if ctx["env"]:
        params["environment"] = ctx["env"]
    result = await client.api("/catalog-page?" + urlencode(params))
    ctx.update(
        rows=result["items"], total=result["total"], page=result["page"], size=result["page_size"]
    )


SCREENS = (
    Screen(
        "catalog",
        "APIカタログ",
        catalog_view,
        load_catalog,
        group="ワークスペース",
        order=20,
    ),
    Screen(
        "inventory",
        "提供するAPI",
        catalog_view,
        load_catalog,
        group="提供者メニュー",
        order=110,
        visible=lambda user: bool(user["owners"]),
        heading_action=lambda: btn("APIを登録", go, "register", primary=True),
    ),
)
