"""部署とプロジェクトの表示を組み立てる。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from actions.workspace import KINDS, kind_label, location, toggle
from puepy import t
from routing.portal_navigation import load
from runtime.portal_ui import ctx

from components import credential_views
from components import workspace_views as directory
from components.controls import btn, field
from components.page_heading import page_heading
from components.workspace_members import members_view, membership_editor
from components.workspace_monitor import monitoring_view


def page_title() -> str:
    """組織の種類と操作から見出しを作る。"""
    root, parts = location()
    label = kind_label(root)[1]
    suffix = {
        "create": "の作成",
        "edit": "の編集",
        "detail": "の詳細",
        "monitor": "のモニタリング",
        "member": "の所属設定",
    }
    if root.startswith("attributes/"):
        label += "の値"
    return label + suffix.get(parts[0] if parts else "", "一覧")


def usage_settings(unit: dict[str, Any], state: dict[str, Any]) -> None:
    """利用停止と有効期限の編集操作を表示する。"""
    with t.section(classes="box"):
        t.h3("利用設定")
        with t.div(classes="btn-grouping"):
            btn("利用を再開" if unit["stopped"] else "利用を停止", toggle, unit)
            credential_views.limit_view(state, field, btn, load, kind="units", identifier=unit["id"])


@dataclass(frozen=True)
class UnitView:
    """組織の詳細と操作欄が共有する表示対象。"""

    root: str
    parts: list[str]
    unit: dict[str, Any]
    data: dict[str, Any]
    by_id: dict[str, dict[str, Any]]
    paths: dict[str, str]
    managed: bool


def detail_panel(target: UnitView) -> None:
    """所属メンバーと管理者向けの操作を表示する。"""
    root, unit = target.root, target.unit
    if root in KINDS:
        t.p(directory.unit_state(unit, target.by_id))
    with t.div(classes="btn-grouping"):
        if target.data["admin"]:
            directory.link(
                kind_label(root)[1] + "を編集", directory.url(root, "edit", unit["id"]), button=True
            )
        if target.managed:
            directory.link("モニタリング", directory.url(root, "monitor", unit["id"]), button=True)
    members_view(root, unit, target.data)
    if target.managed:
        usage_settings(unit, ctx)
    if target.data["admin"]:
        directory.retirement_form(root, kind_label(root)[1], unit, target.by_id, target.paths)


def edit_panel(target: UnitView) -> None:
    """管理者に組織名と親部署の編集欄を表示する。"""
    if len(target.parts) == 2 and target.data["admin"]:
        kind, label = kind_label(target.root)
        directory.unit_editor(target.root, kind, label, target.by_id, target.paths, target.unit)
    else:
        unavailable()


def monitor_panel(target: UnitView) -> None:
    """組織を管理できる利用者に集計を表示する。"""
    if len(target.parts) == 2 and target.managed:
        monitoring_view(target.unit, target.paths)
    else:
        unavailable()


def membership_panel(target: UnitView) -> None:
    """管理者に対象者の所属編集欄を表示する。"""
    if len(target.parts) in (2, 3) and target.data["admin"]:
        subject = target.parts[2] if len(target.parts) == 3 else None
        membership_editor(target.root, target.unit, target.data, subject)
    else:
        unavailable()


def unavailable() -> None:
    """表示できない組織操作の案内を描画する。"""
    t.p("この画面は利用できません。")


def view(draw: Callable[[UnitView], None] | None = None) -> None:
    """組織の一覧・詳細・編集・集計を組み立てる。"""
    root, parts = location()
    kind, label = kind_label(root)
    data = ctx.get("workspace")
    if data is None:
        t.p("一覧を取得できませんでした。")
        btn("再読み込み", load)
        return
    if not label:
        t.p("メタデータ項目が見つかりません。")
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
    managed = root in KINDS and (data["admin"] or unit["id"] in data["leads"])
    with t.div(classes="resource-heading"):
        t.h2(paths[unit["id"]])
        t.span(unit["id"], classes="mono")
    target = UnitView(root, parts, unit, data, by_id, paths, managed)
    if parts[0] == "detail" and len(parts) == 2:
        detail_panel(target)
        return
    directory.link("詳細に戻る", directory.url(root, "detail", unit["id"]))
    # 旧URLやパーセント符号化された操作名でも同じ権限検査を通す。
    panel = draw or {"edit": edit_panel, "monitor": monitor_panel, "member": membership_panel}.get(
        parts[0]
    )
    if panel:
        panel(target)
    else:
        unavailable()


def list_heading(root: str) -> None:
    """組織一覧に見出しを付ける。"""
    page_heading(kind_label(root)[1] + "一覧")
    t.span("使用中のデータパーツ", classes="metadata-badge")
    view()
