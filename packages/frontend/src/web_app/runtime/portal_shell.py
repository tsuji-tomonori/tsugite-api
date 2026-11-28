# 全画面に共通するヘッダーとナビゲーションを描画する。
from __future__ import annotations

from typing import Any

from components.controls import btn
from components.header_search import header_search
from js import document, window
from pages.login import login_page
from puepy import Page, t
from routing.portal_navigation import go
from routing.screen_registry import menu, resolve

from runtime.portal_session import logout
from runtime.portal_ui import action, ctx, role_title, route, value


def theme_changed(event: Any) -> None:
    """選んだ表示モードを保存する。"""
    mode = str(event.target.value)
    window.localStorage.setItem("visual-mode", mode)
    document.documentElement.setAttribute("data-mode", mode)


def set_navigation(opened: bool) -> None:
    """ナビゲーションの開閉状態を反映する。"""
    ctx["nav_open"] = opened
    workspace = document.getElementById("workspace")
    if workspace:
        workspace.setAttribute("data-nav", "open" if opened else "closed")
        document.getElementById("nav-toggle").setAttribute(
            "aria-expanded", "true" if opened else "false"
        )


def toggle_navigation(event: Any) -> None:
    """ボタン操作でメニューを開閉する。"""
    set_navigation(str(event.currentTarget.getAttribute("aria-expanded")) != "true")


def adapt_navigation(event: Any) -> None:
    """画面幅に合わせてメニューを開閉する。"""
    set_navigation(not event.matches)


async def global_search() -> None:
    """ヘッダーの検索語でカタログを開く。"""
    await go("catalog", query=value("global-query"))


class Portal(Page):
    def populate(self) -> None:
        """ログイン状態に合わせて共通レイアウトを描画する。"""
        user, page = ctx["me"], route()
        screen = resolve(page) if user else None
        title = screen.page_title() if screen else "画面が見つかりません"
        active = (screen.parent or screen.path) if screen else ""
        nav_open = ctx.get("nav_open", not window.matchMedia("(max-width: 780px)").matches)
        with t.header(classes="mast"):
            with t.div(classes="identity"):
                t.span("", classes="brand-mark", aria_hidden="true")
                t.strong("継手API", classes="brand")
                t.span("APIポータル", classes="product")
            if user:
                header_search(global_search)
            with t.label(classes="mode-control"):
                t.span("表示", classes="mode-label")
                with t.select(aria_label="表示モード", on_change=theme_changed):
                    for key, label in (("auto", "端末設定"), ("light", "ライト"), ("dark", "ダーク")):
                        t.option(
                            label,
                            value=key,
                            selected=key == (window.localStorage.getItem("visual-mode") or "auto"),
                        )
            if user:
                with t.button(
                    type="button",
                    classes="bell-button",
                    aria_label="通知を開く（未読" + str(ctx["badge"]) + "件）",
                    on_click=action(go, "notifications"),
                ):
                    t.span("", classes="bell-icon", aria_hidden="true")
                    t.strong(str(ctx["badge"]) if ctx["badge"] else "", id="unread-count")
                t.span(
                    " / ".join(sorted(set(user["owners"] + user["projects"]))) or role_title(),
                    classes="project",
                )
                btn("ログアウト", logout)
        if not ctx["config"] or not user:
            with t.section(classes="login box"):
                if ctx["message"]:
                    t.div(
                        ctx["message"],
                        role="alert" if ctx["error"] else "status",
                        classes="notice error" if ctx["error"] else "notice",
                    )
                if ctx["config"]:
                    login_page()
                else:
                    t.p("カタログを読み込み中…")
            return
        with t.div(classes="console-tools"):
            with t.button(
                type="button",
                id="nav-toggle",
                classes="menu-button",
                aria_label="ナビゲーション",
                aria_controls="portal-nav",
                aria_expanded="true" if nav_open else "false",
                on_click=toggle_navigation,
            ):
                t.span("", classes="menu-icon", aria_hidden="true")
            with t.div(classes="crumb", aria_label="現在地"):
                t.a("継手API", href="#/home")
                t.span("›", aria_hidden="true")
                t.strong(title)
            if active != "guide":
                t.a(
                    "使い方ガイド",
                    href="#/guide",
                    classes="guide-shortcut",
                    on_click=action(go, "guide"),
                )
        with t.div(id="workspace", classes="workspace", data_nav="open" if nav_open else "closed"):
            with t.nav(id="portal-nav", classes="rail", aria_label="ポータル"):
                t.strong("継手API", classes="rail-title")
                for label, entries in menu(user).items():
                    with t.div(classes="nav-group"):
                        t.small(label)
                        for entry in entries:
                            selected = active == entry.path or (
                                entry.menu_paths
                                and (page == entry.path or page.startswith(entry.path + "/"))
                            )
                            t.button(
                                entry.page_title(),
                                type="button",
                                classes="nav-item active" if selected else "nav-item",
                                aria_current="page" if selected else "false",
                                on_click=action(go, entry.path),
                            )
            with t.section(classes="content"):
                if ctx["message"]:
                    t.div(
                        ctx["message"],
                        role="alert",
                        classes="notice error" if ctx["error"] else "notice",
                    )
                if not screen:
                    t.h1(title)
                    return
                if not screen.own_heading:
                    with t.div(classes="page-heading"):
                        with t.div():
                            t.h1(title)
                            if screen.description:
                                t.p(screen.description, classes="subtitle")
                        if screen.heading_action:
                            screen.heading_action()
                screen.view()
