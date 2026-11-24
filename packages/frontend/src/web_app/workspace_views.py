"""部署とプロジェクトの一覧および基本設定。"""

from urllib.parse import quote

import client
from js import window
from portal_navigation import go
from portal_ui import action, btn, ctx, field, value
from puepy import t

PAGE_SIZE = 10


def url(root, *parts):
    return "/".join([root, *(quote(str(part), safe="") for part in parts)])


def endpoint(unit):
    return "/workspace/units/" + quote(unit["id"], safe="")


async def navigate(path):
    await go(path)
    window.scrollTo(0, 0)


def link(label, path, *, button=False):
    attrs = {"classes": "btn btn-outline-secondary"} if button else {}
    t.a(label, href="#/" + path, on_click=action(navigate, path), **attrs)


def ancestors(unit, by_id):
    seen = set()
    while unit and unit["id"] not in seen:
        seen.add(unit["id"])
        yield unit
        unit = by_id.get(unit.get("parent"))


def unit_paths(by_id):
    return {
        key: " / ".join(reversed([u["name"] for u in ancestors(unit, by_id)]))
        for key, unit in by_id.items()
    }


def unit_state(unit, by_id):
    for parent in ancestors(unit, by_id):
        if parent["stopped"]:
            return "利用停止中" if parent == unit else parent["name"] + "の設定により利用停止中"
    return "利用可能"


def list_view(root, label, kind, data, by_id, paths, number):
    custom = root.startswith("attributes/")
    rows = sorted(
        (u for u in by_id.values() if u["kind"] == kind), key=lambda u: (paths[u["id"]], u["id"])
    )
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    number = max(1, min(pages, number))
    start = (number - 1) * PAGE_SIZE
    own = set(data["my_units"])
    with t.section(classes="box"):
        with t.div(classes="results-head"):
            t.strong(f"{len(rows)} 件")
            if data["admin"]:
                link("値を追加" if custom else label + "を作成", root + "/create", button=True)
        if not rows:
            t.p(label + "は登録されていません。")
            return
        with t.div(classes="resource-table", tabindex="0", role="region", aria_label=label + "一覧"):
            with t.table(aria_label=label + "一覧"):
                with t.thead():
                    with t.tr():
                        for title in (
                            "名称",
                            "識別子",
                            "上位の値" if custom else "親部署",
                            *([] if custom else ["利用状態"]),
                            "自分の所属",
                        ):
                            t.th(title, scope="col")
                with t.tbody():
                    for row in rows[start : start + PAGE_SIZE]:
                        with t.tr():
                            with t.th(scope="row"):
                                link(row["name"], url(root, "detail", row["id"]))
                            t.td(row["id"], classes="mono")
                            t.td(paths.get(row.get("parent"), "—"))
                            if not custom:
                                t.td(unit_state(row, by_id))
                            t.td("所属" if row["id"] in own else "—")
        with t.nav(classes="pager", aria_label=label + "一覧のページ"):
            if number > 1:
                link("前へ", url(root, "page", number - 1), button=True)
            t.span(
                f"{start + 1}–{min(start + PAGE_SIZE, len(rows))} 件 / 全 {len(rows)} 件（{number} / {pages} ページ）"
            )
            if number < pages:
                link("次へ", url(root, "page", number + 1), button=True)


def unit_editor(root, kind, label, by_id, paths, unit=None):
    draft = unit or {}

    async def save():
        key = draft["id"] if unit else value("org-unit-id")
        if not key or not value("org-unit-name"):
            raise client.InputError("名称と識別子を入力してください")
        if not unit and key in by_id:
            raise client.InputError("この識別子は既に使われています")
        await client.api(
            "/workspace/units/" + quote(key, safe=""),
            "PUT",
            {"name": value("org-unit-name"), "kind": kind, "parent": value("org-parent")},
        )
        await navigate(url(root, "detail", key))
        ctx["message"] = label + "を保存しました"

    with t.section(classes="box"):
        field("名称", "org-unit-name", text=draft.get("name", ""))
        if not unit:
            field("識別子", "org-unit-id", placeholder="例　sales-west")
        custom = root.startswith("attributes/")
        parents = [
            (k, paths[k])
            for k, row in by_id.items()
            if row["kind"] == (kind if custom else "department")
            and all(a["id"] != draft.get("id") for a in ancestors(row, by_id))
        ]
        field(
            "上位の値" if custom else "親部署",
            "org-parent",
            options=[("", "指定なし"), *sorted(parents, key=lambda p: p[1])],
            text=draft.get("parent") or "",
        )
        with t.div(classes="btn-grouping"):
            btn("保存", save, primary=True)
            link("キャンセル", url(root, "detail", unit["id"]) if unit else root, button=True)


def retirement_form(root, label, unit, by_id, paths):
    key = unit["id"]
    candidates = sorted(
        (other, paths[other])
        for other, row in by_id.items()
        if row["kind"] == unit["kind"] and key not in {u["id"] for u in ancestors(row, by_id)}
    )

    async def remove():
        if window.confirm(f"{unit['name']}（{key}）を削除しますか？"):
            await client.api(endpoint(unit), "DELETE")
            await navigate(root)
            ctx["message"] = label + "を削除しました"

    async def transfer():
        destination = value("unit-destination")
        if destination not in dict(candidates):
            raise client.InputError("移管先を選択してください")
        if window.confirm(f"{paths[key]} を {paths[destination]} へ移管し、移管元を廃止しますか？"):
            await client.api(endpoint(unit) + "/transfer", "POST", {"destination": destination})
            await navigate(url(root, "detail", destination))
            ctx["message"] = label + "を移管しました"

    with t.details(classes="box"):
        t.summary("移管・削除")
        if root.startswith("attributes/"):
            t.p("同じ項目の別の値に、所属者と下位の値を移管します。")
        else:
            t.p("移管すると、所属者・配下の組織・API商品・利用権・認証情報を移管先に引き継ぎます。")
            t.p("移管先の所属者にも共有の利用権が適用されます。監査履歴には当時の識別子が残ります。")
        field("移管先", "unit-destination", options=[("", "選択してください"), *candidates])
        btn(label + "を移管", transfer)
        t.p("所属者や利用中の設定がない組織は削除できます。廃止した識別子は再使用できません。")
        btn(label + "を削除", remove)
