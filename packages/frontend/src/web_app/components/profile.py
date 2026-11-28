# 利用者プロフィールの編集欄を表示する。
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from actions.profile import load_profile, profile_endpoint, save
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx, route

from components.controls import btn, field
from components.workspace_views import unit_paths


def view() -> None:
    """本人または管理対象者のプロフィールを表示する。"""
    page = route()
    if page != "profile" and not ctx["me"]["admin"]:
        t.p("プロフィールの管理には管理者の権限が必要です。")
        return
    profile = ctx.get("member_profile")
    if profile is None:
        return
    with t.section(classes="box"):
        t.p("メールアドレス　" + (profile["email"] or "—"))
        field("氏名", "profile-full-name", text=profile["full_name"] or "", required=True)
        field("表示名", "profile-display-name", text=profile["display_name"] or "", required=False)
        with t.div(classes="btn-grouping"):
            btn("保存する", save, profile_endpoint(page), profile["revision"], primary=True)
            btn("再読み込み", load_profile, page)
            if page != "profile":
                btn("ユーザー管理に戻る", go, "members")

    directory = ctx.get("profile_directory")
    if directory:
        subject = ctx["me"]["subject"] if page == "profile" else unquote(page.partition("/")[2])
        person_metadata(directory, subject)


def person_metadata(directory: dict[str, Any], subject: str) -> None:
    """所属する属性値とグループ内の役割を表示する。"""
    units = {unit["id"]: unit for unit in directory["units"]}
    paths = unit_paths(units)
    rows = {r["unit_id"]: r for r in directory["memberships"] if r["subject"] == subject}
    if subject == ctx["me"]["subject"]:
        for key in directory["my_units"]:
            rows.setdefault(key, {})
    with t.section(classes="box"):
        t.h2("利用者のメタデータ")
        with t.div(classes="resource-table"), t.table(aria_label="利用者のメタデータ"):
            with t.thead(), t.tr():
                for label in ("項目", "設定されている値", "グループ内の役割"):
                    t.th(label, scope="col")
            with t.tbody():
                for item in directory["metadata_fields"]:
                    for key in sorted(rows, key=lambda k: paths.get(k, k)):
                        if units.get(key, {}).get("kind") != item["key"]:
                            continue
                        with t.tr():
                            t.th(item["label"], scope="row")
                            t.td(paths[key])
                            row = rows[key]
                            t.td(
                                " / ".join(
                                    filter(
                                        None, ["リーダー" if row.get("leader") else "", row.get("title")]
                                    )
                                )
                                or "—"
                            )
        if not rows:
            t.p("設定されている値はありません。")
