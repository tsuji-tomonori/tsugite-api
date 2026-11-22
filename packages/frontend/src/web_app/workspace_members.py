"""選択した部署またはプロジェクトの所属設定。"""

from urllib.parse import urlencode

import client
from js import window
from portal_navigation import load
from portal_ui import btn, ctx, field, value
from puepy import t
from workspace_views import link, navigate, url


def members_view(root, unit, data):
    key = unit["id"]
    rows = [r for r in data["memberships"] if r["unit_id"] == key]
    names = {u["subject"]: u["username"] for u in data["users"]}

    async def remove(row):
        if window.confirm(
            f"{unit['name']} から {names.get(row['subject'], row['subject'])} の所属を解除しますか？"
        ):
            params = urlencode({"unit_id": key, "subject": row["subject"]})
            await client.api("/workspace/memberships?" + params, "DELETE")
            await load()
            ctx["message"] = "所属を解除しました"

    with t.section(classes="box"):
        with t.div(classes="results-head"):
            t.h3("直接の所属メンバー")
            if data["admin"]:
                link("メンバーを追加", url(root, "member", key), button=True)
        if not rows:
            t.p("表示できるメンバーはいません。")
        for row in rows:
            subject = row["subject"]
            with t.div(classes="compact-row"):
                t.strong(row.get("username") or names.get(subject, subject))
                t.span(row.get("title") or "役職未設定")
                t.span("リーダー" if row["leader"] else "メンバー")
                if data["admin"]:
                    link("所属を編集", url(root, "member", key, subject), button=True)
                    btn("所属を解除", remove, row)


def membership_editor(root, unit, data, subject):
    key = unit["id"]
    members = {r["subject"]: r for r in data["memberships"] if r["unit_id"] == key}
    if subject is not None and subject not in members:
        t.p("所属が見つかりません。")
        return
    row = members.get(subject, {})
    draft = ctx.get("member_form", {})
    names = {u["subject"]: u["username"] for u in data["users"]}
    names.update(draft.get("names", {}))
    detail = url(root, "detail", key)

    async def more():
        params = urlencode({"cursor": draft.get("next", "")})
        response = await client.api("/members?" + params)
        names.update({u["subject"]: u["username"] for u in response["items"] if not u.get("deleted")})
        ctx["member_form"] = {
            "names": names,
            "next": response["next"],
            "subject": value("org-subject"),
            "title": value("org-title"),
            "role": value("org-leader"),
        }

    async def save():
        selected = subject or value("org-subject")
        if not selected:
            raise client.InputError("ユーザーを選択してください")
        await client.api(
            "/workspace/memberships",
            "PUT",
            {
                "subject": selected,
                "unit_id": key,
                "title": value("org-title"),
                "leader": value("org-leader") == "yes",
            },
        )
        await navigate(detail)
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
            t.p("ユーザー　" + (row.get("username") or names.get(subject, subject)))
        field("役職", "org-title", text=draft.get("title", row.get("title", "")), placeholder="例　課長")
        field(
            "管理権限",
            "org-leader",
            options=[("no", "メンバー"), ("yes", "リーダー")],
            text=draft.get("role", "yes" if row.get("leader") else "no"),
        )
        with t.div(classes="btn-grouping"):
            btn("所属を保存", save, primary=True)
            link("キャンセル", detail, button=True)
