"""部署とプロジェクトの一覧・編集部品を描画する。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

from apis import client
from apis import organization as organization_api
from js import window
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import action, ctx, value

from components.controls import btn, field
from components.list_layout import result_table

PAGE_SIZE = 10


def url(root: str, *parts: str | int) -> str:
    """組織内の操作URLを作る。"""
    return "/".join([root, *(quote(str(part), safe="") for part in parts)])


def endpoint(unit: dict[str, Any]) -> str:
    """組織に対応するAPIパスを作る。"""
    return "/workspace/units/" + quote(unit["id"], safe="")


def link(label: str, path: str, *, button: bool = False) -> None:
    """組織画面へのリンクを描画する。"""
    attrs = {"classes": "btn btn-outline-secondary"} if button else {}
    t.a(label, href="#/" + path, on_click=action(go, path), **attrs)


def ancestors(unit: dict[str, Any] | None, by_id: dict[str, dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """親組織を循環せずにたどる。"""
    seen = set()
    while unit and unit["id"] not in seen:
        seen.add(unit["id"])
        yield unit
        unit = by_id.get(unit.get("parent") or "")


def unit_paths(by_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    """組織IDから階層名を引ける辞書を作る。"""
    return {
        key: " / ".join(reversed([u["name"] for u in ancestors(unit, by_id)]))
        for key, unit in by_id.items()
    }


def unit_state(unit: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    """上位組織から継承する停止状態を表示名にする。"""
    for parent in ancestors(unit, by_id):
        if parent["stopped"]:
            return "利用停止中" if parent == unit else parent["name"] + "の設定により利用停止中"
    return "利用可能"


def list_view(
    root: str,
    label: str,
    kind: str,
    data: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    paths: dict[str, str],
    number: int,
) -> None:
    """組織一覧をページ単位で描画する。"""
    custom = root.startswith("attributes/")
    rows = sorted(
        (u for u in by_id.values() if u["kind"] == kind), key=lambda u: (paths[u["id"]], u["id"])
    )
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    number = max(1, min(pages, number))
    start = (number - 1) * PAGE_SIZE
    own = set(data["my_units"])
    with t.div(classes="list-tools"):
        t.strong(f"{len(rows)} 件")
        if data["admin"]:
            link("値を追加" if custom else label + "を作成", root + "/create", button=True)
    if not rows:
        t.p(label + "は登録されていません。")
        return
    columns = (
        ("名称", "識別子", "上位の値", "自分の所属")
        if custom
        else ("名称", "識別子", "親部署", "利用状態", "自分の所属")
    )
    with result_table(label + "一覧", columns):
        for row in rows[start : start + PAGE_SIZE]:
            with t.tr():
                with t.th(scope="row"):
                    link(row["name"], url(root, "detail", row["id"]))
                t.td(row["id"], classes="mono")
                t.td(paths.get(row.get("parent") or "", "—"))
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


def unit_editor(
    root: str,
    kind: str,
    label: str,
    by_id: dict[str, dict[str, Any]],
    paths: dict[str, str],
    unit: dict[str, Any] | None = None,
) -> None:
    """組織の作成・編集フォームを描画する。"""
    draft = unit or {}

    async def save() -> None:
        key = draft["id"] if unit else value("org-unit-id")
        if not key or not value("org-unit-name"):
            raise client.InputError("名称と識別子を入力してください")
        if not unit and key in by_id:
            raise client.InputError("この識別子は既に使われています")
        await organization_api.save_unit(
            key, {"name": value("org-unit-name"), "kind": kind, "parent": value("org-parent")}
        )
        await go(url(root, "detail", key))
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


def retirement_form(
    root: str, label: str, unit: dict[str, Any], by_id: dict[str, dict[str, Any]], paths: dict[str, str]
) -> None:
    """組織の移管と削除操作を表示する。"""
    key = unit["id"]
    candidates = sorted(
        (other, paths[other])
        for other, row in by_id.items()
        if row["kind"] == unit["kind"] and key not in {u["id"] for u in ancestors(row, by_id)}
    )

    async def remove() -> None:
        if window.confirm(f"{unit['name']}（{key}）を削除しますか？"):
            await organization_api.delete_unit(endpoint(unit))
            await go(root)
            ctx["message"] = label + "を削除しました"

    async def transfer() -> None:
        destination = value("unit-destination")
        if destination not in dict(candidates):
            raise client.InputError("移管先を選択してください")
        if window.confirm(f"{paths[key]} を {paths[destination]} へ移管し、移管元を廃止しますか？"):
            await organization_api.transfer_unit(endpoint(unit), {"destination": destination})
            await go(url(root, "detail", destination))
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
