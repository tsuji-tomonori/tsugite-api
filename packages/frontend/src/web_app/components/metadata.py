"""メタデータの一覧と項目編集を表示する。"""

from __future__ import annotations

from apis import client
from apis import organization as organization_api
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx, route, value

from components.controls import btn, field
from components.workspace_views import link

BUILTIN_ROUTES = {"department": "departments", "project": "projects"}


def field_list() -> None:
    """項目とデータパーツの利用状態を表示する。"""
    data = ctx.get("workspace")
    if not data:
        return
    with t.section(classes="box"):
        if data["admin"]:
            link("項目を追加", "metadata/create", button=True)
        with t.div(classes="resource-table"), t.table(aria_label="メタデータ項目"):
            with t.thead(), t.tr():
                for label in ("項目", "キー", "データパーツ", "値の公開範囲"):
                    t.th(label, scope="col")
                if data["admin"]:
                    t.th("設定", scope="col")
            with t.tbody():
                for item in data["metadata_fields"]:
                    key = item["key"]
                    with t.tr():
                        with t.th(scope="row"):
                            link(item["label"], BUILTIN_ROUTES.get(key, "attributes/" + key))
                        t.td(key)
                        with t.td():
                            if item["builtin"]:
                                t.span("使用中", classes="metadata-badge")
                            else:
                                t.span("任意項目")
                        t.td("全利用者" if item["public_values"] else "所属者・管理者")
                        if data["admin"]:
                            with t.td():
                                if not item["builtin"]:
                                    link("設定を編集", "metadata/edit/" + key)
                                else:
                                    t.span("組み込み")


def field_editor() -> None:
    """メタデータの項目設定を描画する。"""
    data = ctx.get("workspace")
    if not data or not data["admin"]:
        t.p("項目の設定には管理者の権限が必要です。")
        return
    parts = route().split("/")
    fields = {item["key"]: item for item in data["metadata_fields"]}
    editing = len(parts) == 3 and parts[1] == "edit"
    item = fields.get(parts[-1], {}) if editing else {}
    if parts != ["metadata", "create"] and (not editing or not item or item["builtin"]):
        t.p("編集できる項目が見つかりません。")
        return

    async def save() -> None:
        key = item["key"] if editing else value("metadata-key")
        label = value("metadata-label")
        if not key or not label:
            raise client.InputError("項目名とキーを入力してください")
        if not editing and key in fields:
            raise client.InputError("このキーは使われています")
        await organization_api.save_field(
            key,
            {"label": label, "public_values": value("metadata-scope") == "all"},
        )
        await go("metadata")
        ctx["message"] = "メタデータ項目を保存しました"

    with t.section(classes="box"):
        field(
            "項目名",
            "metadata-label",
            text=item.get("label", ""),
            placeholder="例　雇用区分",
            required=True,
        )
        if editing:
            t.p("キー　" + item["key"])
        else:
            field("キー", "metadata-key", placeholder="例　employment-type", required=True)
        field(
            "値の名称を見られる人",
            "metadata-scope",
            options=[("assigned", "所属者・管理者"), ("all", "全利用者")],
            text="all" if item.get("public_values") else "assigned",
        )
        with t.div(classes="btn-grouping"):
            btn("保存", save, primary=True)
            link("キャンセル", "metadata", button=True)
