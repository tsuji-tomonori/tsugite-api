from urllib.parse import unquote

import client
import credential_views
import workspace_views as directory
from js import window
from portal_navigation import load
from portal_ui import btn, ctx, field, route
from puepy import t
from screen_registry import Screen
from workspace_members import members_view, membership_editor
from workspace_monitor import monitoring_view

KINDS = {"departments": ("department", "部署"), "projects": ("project", "プロジェクト")}


def location():
    root, *parts = route().split("/")
    return ("departments" if root == "workspace" else root), [unquote(part) for part in parts]


def page_title():
    root, parts = location()
    label = KINDS[root][1]
    suffix = {
        "create": "の作成",
        "edit": "の編集",
        "detail": "の詳細",
        "monitor": "のモニタリング",
        "member": "の所属設定",
    }
    return label + suffix.get(parts[0] if parts else "", "一覧")


async def load_workspace(page):
    for key in ("workspace", "workspace_usage", "member_form"):
        ctx.pop(key, None)
    data = await client.api("/workspace")
    if page != route():
        return
    ctx["workspace"] = data
    root, parts = location()
    if len(parts) == 2 and parts[0] == "monitor":
        unit = next(
            (u for u in data["units"] if u["id"] == parts[1] and u["kind"] == KINDS[root][0]), None
        )
        if unit and (data["admin"] or unit["id"] in data["leads"]):
            usage = await client.api(directory.endpoint(unit) + "/usage")
            if page == route():
                ctx["workspace_usage"] = usage


def view():
    root, parts = location()
    kind, label = KINDS[root]
    data = ctx.get("workspace")
    if data is None:
        t.p("一覧を取得できませんでした。")
        btn("再読み込み", load)
        return
    by_id = {u["id"]: u for u in data["units"]}
    paths = directory.unit_paths(by_id)
    if not parts or (
        len(parts) == 2
        and parts[0] == "page"
        and parts[1].isascii()
        and parts[1].isdecimal()
        and len(parts[1]) < 10
    ):
        directory.list_view(root, label, kind, data, by_id, paths, int(parts[1]) if parts else 1)
        return
    directory.link(label + "一覧に戻る", root)
    if parts == ["create"] and data["admin"]:
        directory.unit_editor(root, kind, label, by_id, paths)
        return
    unit = by_id.get(parts[1]) if len(parts) >= 2 else None
    if not unit or unit["kind"] != kind:
        t.p("対象が見つかりません。")
        return
    managed = data["admin"] or unit["id"] in data["leads"]
    detail = directory.url(root, "detail", unit["id"])
    with t.div(classes="resource-heading"):
        t.h2(paths[unit["id"]])
        t.span(unit["id"], classes="mono")
    if len(parts) == 2 and parts[0] == "detail":
        t.p(directory.unit_state(unit, by_id))
        with t.div(classes="btn-grouping"):
            if data["admin"]:
                directory.link(label + "を編集", directory.url(root, "edit", unit["id"]), button=True)
            if managed:
                directory.link("モニタリング", directory.url(root, "monitor", unit["id"]), button=True)
        members_view(root, unit, data)
        if managed:
            with t.section(classes="box"):
                t.h3("利用設定")
                with t.div(classes="btn-grouping"):
                    btn("利用を再開" if unit["stopped"] else "利用を停止", toggle, unit)
                    credential_views.limit_view(
                        ctx, field, btn, load, kind="units", identifier=unit["id"]
                    )
        return
    directory.link("詳細に戻る", detail)
    if parts[0] == "edit" and len(parts) == 2 and data["admin"]:
        directory.unit_editor(root, kind, label, by_id, paths, unit)
    elif parts[0] == "monitor" and len(parts) == 2 and managed:
        monitoring_view(unit, paths)
    elif parts[0] == "member" and len(parts) in (2, 3) and data["admin"]:
        membership_editor(root, unit, data, parts[2] if len(parts) == 3 else None)
    else:
        t.p("この画面は利用できません。")


async def toggle(unit):
    stopped = not unit["stopped"]
    verb = "停止" if stopped else "再開"
    if window.confirm(unit["name"] + " のAPI利用を" + verb + "しますか？"):
        await client.api(directory.endpoint(unit) + "/state", "PUT", {"stopped": stopped})
        await load()
        ctx["message"] = "API利用を" + verb + "しました"


def list_screen(root, order):
    def with_heading():
        t.h1(KINDS[root][1] + "一覧")
        view()

    return Screen(
        root,
        KINDS[root][1],
        with_heading,
        load_workspace,
        group="ワークスペース",
        order=order,
        own_heading=True,
    )


SCREENS = (
    list_screen("departments", 60),
    list_screen("projects", 61),
    Screen("departments/", page_title, view, load_workspace, parent="departments"),
    Screen("projects/", page_title, view, load_workspace, parent="projects"),
    Screen("workspace", "部署一覧", view, load_workspace, parent="departments"),
)
