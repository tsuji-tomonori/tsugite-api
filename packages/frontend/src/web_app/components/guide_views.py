# 使い方ガイドの一覧と記事を描画する。
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from content.guide_content import BY_ID, GUIDES, audiences
from content.guide_search import search
from js import document
from puepy import t

ROLES = ("すべて", "利用者", "提供者", "管理者")


def index(ctx: dict[str, Any]) -> None:
    """検索可能なガイド一覧を表示する。"""
    query = ctx.get("guide_query", "")
    role = ctx.get("guide_role", ROLES[0])

    def update(event: Any) -> None:
        event.preventDefault()
        ctx["guide_query"] = str(document.getElementById("guide-query").value)
        ctx["guide_role"] = str(document.getElementById("guide-role").value)
        matches = search(ctx["guide_query"], ctx["guide_role"])
        grid = document.getElementById("guide-grid")
        visible = {g.id for g in matches}
        for g in GUIDES:
            document.getElementById("guide-card-" + g.id).hidden = g.id not in visible
        for g in matches:
            grid.appendChild(document.getElementById("guide-card-" + g.id))
        document.getElementById("guide-count").textContent = f"{len(matches)}件"
        document.getElementById("guide-empty").hidden = bool(matches)
        document.getElementById("guide-clear").hidden = not (
            ctx["guide_query"] or ctx["guide_role"] != ROLES[0]
        )

    def reset(event: Any) -> None:
        document.getElementById("guide-query").value = ""
        document.getElementById("guide-role").value = ROLES[0]
        update(event)
        document.getElementById("guide-query").focus()

    with t.form(classes="box guide-search", on_submit=update):
        with t.label(classes="field"):
            t.span("何をしたいですか？")
            t.input(
                type="search",
                id="guide-query",
                classes="form-control",
                value=query,
                on_input=update,
                placeholder="例　APIを使いたい、読み取りだけ許可したい",
            )
        with t.label(classes="field"):
            t.span("役割", id="guide-role-label")
            with t.select(
                id="guide-role",
                aria_labelledby="guide-role-label",
                classes="form-select",
                on_change=update,
            ):
                for label in ROLES:
                    t.option(label, value=label, selected=label == role)
        t.button("ガイドを検索", type="submit", classes="btn btn-primary")

    results = search(query, role)
    with t.div(classes="guide-results"):
        t.h2("操作手順")
        t.span(f"{len(results)}件", id="guide-count", role="status")
        t.button(
            "条件をクリア",
            id="guide-clear",
            hidden=not (query or role != ROLES[0]),
            type="button",
            classes="btn btn-outline-secondary",
            on_click=reset,
        )
    t.p(
        "手順が見つかりませんでした。役割を［すべて］にするか、画面名や別の言葉で検索してください。",
        id="guide-empty",
        hidden=bool(results),
        classes="empty",
    )
    with t.div(classes="guide-grid", id="guide-grid"):
        for g in [*results, *(g for g in GUIDES if g not in results)]:
            with t.article(classes="box", id="guide-card-" + g.id, hidden=g not in results):
                t.small("・".join(audiences(g)), classes="muted")
                with t.h3():
                    t.a(g.title, href="#/guide/" + g.id)


def article(
    key: str,
    user: dict[str, Any],
    pages: dict[str, str],
    go: Callable[..., Awaitable[None]],
    btn: Callable[..., object],
    examples: dict[str, Callable[[], None]],
) -> None:
    """手順・画面例・関連操作を表示する。"""
    g = BY_ID.get(key)
    t.a("使い方ガイドの一覧に戻る", href="#/guide")
    if not g:
        t.p("指定された手順が見つかりません。")
        return
    t.p("・".join(audiences(g)) + "向け", classes="muted")
    with t.section(classes="box guide-article"):
        t.p(g.prerequisite)
        with t.ol():
            for step in g.steps:
                t.li(step)
        t.h2("操作後の確認")
        t.p(g.result)
        with t.figure():
            t.figcaption("画面例（閲覧のみ）　" + g.caption)
            with t.div(classes="guide-preview", inert=True):
                examples[g.id]()
        allowed = (
            (g.start != "inventory" or user["owners"])
            and (g.start != "inbox" or user["owners"] or user["leads"])
            and (g.start != "members" or user["admin"])
            and (key != "organization" or user["admin"])
            and (key not in ("suspend", "limits") or user["admin"] or user["leads"])
            and (key not in ("notice", "alerts") or user["admin"] or user["owners"])
        )
        if allowed:
            btn("「" + pages[g.start] + "」を開く", go, g.start, primary=True)

    next_steps = {
        "apply": ("status",),
        "status": ("credential", "invoke"),
        "credential": ("invoke", "rotate"),
        "keys": ("invoke",),
        "invoke": ("logs",),
        "publish": ("visibility", "review"),
        "review": ("operations",),
        "member": ("organization",),
        "metrics": ("logs",),
        "logs": ("audit",),
    }
    if key in next_steps:
        with t.section(classes="box"):
            t.h2("関連する手順")
            with t.ul():
                for related in next_steps[key]:
                    with t.li():
                        t.a(BY_ID[related].title, href="#/guide/" + related)
