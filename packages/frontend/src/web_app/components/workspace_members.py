# 組織の所属メンバーと編集欄を表示する。
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from apis import client
from apis import organization as organization_api
from js import window
from puepy import t
from routing.portal_navigation import go, load
from runtime.portal_ui import ctx, value

from components.controls import btn, field
from components.workspace_views import link, url


def person_label(person: dict[str, Any]) -> str:
    """氏名とメールアドレスから表示名を作る。"""
    name = person.get("display_name") or person.get("full_name")
    address = person.get("email") or person.get("username") or person["subject"]
    return f"{name}（{address}）" if name and name != address else address


def members_view(root: str, unit: dict[str, Any], data: dict[str, Any]) -> None:
    """直接所属するメンバーを表で表示する。"""
    key = unit["id"]
    rows = [r for r in data["memberships"] if r["unit_id"] == key]
    people = {u["subject"]: u for u in data["users"]}

    async def remove(row: dict[str, Any]) -> None:
        if window.confirm(
            f"{unit['name']} から {person_label({**people.get(row['subject'], {}), **row})} の所属を解除しますか？"
        ):
            params = urlencode({"unit_id": key, "subject": row["subject"]})
            await organization_api.remove_membership(params)
            await load()
            ctx["message"] = "所属を解除しました"

    with t.section(classes="box"):
        with t.div(classes="results-head"):
            t.h3("直接の所属メンバー")
            if data["admin"]:
                link("メンバーを追加", url(root, "member", key), button=True)
        if not rows:
            t.p("表示できるメンバーはいません。")
            return
        with (
            t.div(classes="resource-table membership-table", tabindex="0"),
            t.table(aria_label="直接の所属メンバー"),
        ):
            with t.thead(), t.tr():
                for label in ("メールアドレス", "名前", "担当ロール"):
                    t.th(label, scope="col")
                if data["admin"]:
                    t.th("操作", scope="col")
            with t.tbody():
                for row in rows:
                    subject = row["subject"]
                    person = {**people.get(subject, {}), **row}
                    username = person.get("username")
                    email = person.get("email")
                    if "email" not in person and username and "@" in username:
                        email = username
                    full_name, display_name = person.get("full_name"), person.get("display_name")
                    with t.tr():
                        t.td(email or "—")
                        with t.td():
                            t.span(display_name or full_name or "—")
                            if display_name and full_name and display_name != full_name:
                                t.div(full_name, classes="muted")
                            if not (display_name or full_name or email):
                                label = "ログイン名" if username and username != subject else "利用者ID"
                                t.div(f"{label} {username or subject}", classes="muted")
                        with t.td():
                            t.strong("リーダー" if row["leader"] else "メンバー")
                            if row.get("title"):
                                t.div(row["title"], classes="muted")
                        if data["admin"]:
                            with t.td(), t.div(classes="membership-actions"):
                                link("所属を編集", url(root, "member", key, subject), button=True)
                                btn("所属を解除", remove, row)


def membership_editor(
    root: str,
    unit: dict[str, Any],
    data: dict[str, Any],
    subject: str | None,
    *,
    draft: dict[str, Any] | None = None,
) -> None:
    """対象者の所属とリーダー設定を編集する欄を描画する。"""
    key = unit["id"]
    members = {r["subject"]: r for r in data["memberships"] if r["unit_id"] == key}
    if subject is not None and subject not in members:
        t.p("所属が見つかりません。")
        return
    row = members.get(subject, {})
    if draft is None:
        draft = ctx.get("member_form", {})
    names = {u["subject"]: person_label(u) for u in data["users"]}
    names.update(draft.get("names", {}))
    detail = url(root, "detail", key)

    async def more() -> None:
        params = urlencode({"cursor": draft.get("next", "")})
        response = await organization_api.members(params)
        names.update({u["subject"]: person_label(u) for u in response["items"] if not u.get("deleted")})
        ctx["member_form"] = {
            "names": names,
            "next": response["next"],
            "subject": value("org-subject"),
            "title": value("org-title"),
            "role": value("org-leader"),
        }

    async def save() -> None:
        selected = subject or value("org-subject")
        if not selected:
            raise client.InputError("ユーザーを選択してください")
        await organization_api.membership(
            {
                "subject": selected,
                "unit_id": key,
                "title": value("org-title"),
                "leader": value("org-leader") == "yes",
            }
        )
        await go(detail)
        ctx["message"] = "所属と役職を保存しました"

    with t.section(classes="box"):
        if subject is None:
            choices = sorted(((s, n) for s, n in names.items() if s not in members), key=lambda p: p[1])
            field(
                "ユーザー",
                "org-subject",
                options=[("", "選択してください"), *choices],
                text=draft.get("subject", ""),
            )
            if "next" not in draft or draft["next"]:
                with t.div(classes="field-actions"):
                    btn("ユーザーをさらに読み込む" if draft else "登録ユーザーを読み込む", more)
        else:
            t.p("ユーザー　" + person_label({"subject": subject, "username": names.get(subject), **row}))
        field(
            "グループ内の役割" if root.startswith("attributes/") else "役職",
            "org-title",
            text=draft.get("title", row.get("title", "")),
            placeholder="例　課長",
        )
        field(
            "メンバーの閲覧権限" if root.startswith("attributes/") else "管理権限",
            "org-leader",
            options=[("no", "メンバー"), ("yes", "リーダー")],
            text=draft.get("role", "yes" if row.get("leader") else "no"),
        )
        with t.div(classes="btn-grouping"):
            btn("所属を保存", save, primary=True)
            link("キャンセル", detail, button=True)
