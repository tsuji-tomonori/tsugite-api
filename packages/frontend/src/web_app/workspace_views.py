"""Organization directory and leader usage views for the Python portal."""

from urllib.parse import quote, urlencode

import client
import credential_views
from js import document, window
from puepy import t


def _value(name):
    return str(document.getElementById(name).value).strip()


def _unit_paths(units):
    by_id = {unit["id"]: unit for unit in units}
    paths = {}
    for unit in units:
        names = []
        seen = set()
        node = unit
        while node and node["id"] not in seen:
            names.append(node["name"])
            seen.add(node["id"])
            node = by_id.get(node.get("parent"))
        paths[unit["id"]] = " / ".join(reversed(names))
    return paths


def _membership(row, names, paths):
    username = row.get("username") or names.get(row["subject"], row["subject"])
    fields = [username, paths.get(row.get("unit_id"), row.get("unit_id", "")), row.get("title")]
    if row.get("leader"):
        fields.append("リーダー")
    return " · ".join(str(s) for s in fields if s)


def workspace_view(ctx, field, btn, reload):
    directory = ctx["workspace"]
    units = directory["units"]
    paths = _unit_paths(units)
    by_id = {u["id"]: u for u in units}
    units = sorted(units, key=lambda row: paths[row["id"]])
    leads = set(directory.get("leads", []))
    admin = directory["admin"]
    names = {r["subject"]: r["username"] for r in directory.get("users", [])}
    account = ctx["me"]["subject"]
    directory_page = ctx.get("directory_candidates", {})
    if admin and directory_page.get("owner") == account:
        names.update(directory_page["names"])
    else:
        directory_page = {}

    async def edit_unit(row):
        ctx["unit_draft"] = row

    async def save_unit():
        identifier = _value("org-unit-id")
        if not identifier:
            raise ValueError("識別子を入力してください")
        await client.api(
            "/workspace/units/" + quote(identifier, safe=""),
            "PUT",
            {
                "name": _value("org-unit-name"),
                "kind": _value("org-kind"),
                "parent": _value("org-parent"),
            },
        )
        ctx.pop("unit_draft", None)
        ctx.pop("workspace_usage", None)
        await reload()
        ctx["message"] = "組織設定を保存しました"

    async def edit_membership(row):
        ctx["membership_draft"] = row

    async def load_users(cursor):
        draft = {
            "subject": _value("org-subject"),
            "unit_id": _value("org-membership-unit"),
            "title": _value("org-title"),
            "leader": _value("org-leader") == "yes",
        }
        response = await client.api("/members?" + urlencode({"cursor": cursor}))
        users = dict(directory_page.get("names", {}))
        users.update({u["subject"]: u["username"] for u in response["items"] if not u.get("deleted")})
        ctx["directory_candidates"] = {"owner": account, "names": users, "next": response["next"]}
        ctx["membership_draft"] = draft

    async def save_membership():
        await client.api(
            "/workspace/memberships",
            "PUT",
            {
                "subject": _value("org-subject"),
                "unit_id": _value("org-membership-unit"),
                "title": _value("org-title"),
                "leader": _value("org-leader") == "yes",
            },
        )
        ctx.pop("membership_draft", None)
        ctx.pop("workspace_usage", None)
        await reload()
        ctx["message"] = "所属と役職を保存しました"

    async def remove_membership(row):
        if window.confirm(_membership(row, names, paths) + " の所属を解除しますか？"):
            params = urlencode({"subject": row["subject"], "unit_id": row["unit_id"]})
            await client.api("/workspace/memberships?" + params, "DELETE")
            ctx.pop("workspace_usage", None)
            ctx.pop("membership_draft", None)
            await reload()
            ctx["message"] = "所属を解除しました"

    async def show_usage(unit):
        usage = await client.api("/workspace/units/" + quote(unit["id"], safe="") + "/usage")
        ctx["workspace_usage"] = usage

    async def toggle(unit):
        stopped = not unit["stopped"]
        verb = "停止" if stopped else "再開"
        if window.confirm(paths[unit["id"]] + " のAPI利用を" + verb + "しますか？"):
            await client.api(
                "/workspace/units/" + quote(unit["id"], safe="") + "/state", "PUT", {"stopped": stopped}
            )
            ctx.pop("workspace_usage", None)
            await reload()
            ctx["message"] = "API利用を" + verb + "しました"

    with t.section(classes="box"):
        t.h2("自分の所属")
        mine = [r for r in directory["memberships"] if r["subject"] == account]
        if not mine:
            t.p("個別に登録された所属はありません。")
        for row in mine:
            t.p(_membership(row, {}, paths))

    if admin:
        draft = ctx.get("unit_draft") or {}
        with t.details(classes="box", open=bool(draft)):
            t.summary("部署・プロジェクトの登録と編集")
            field("名称", "org-unit-name", text=draft.get("name", ""))
            if draft:
                with t.label(classes="field"):
                    t.span("識別子")
                    t.input(id="org-unit-id", classes="form-control", value=draft["id"], readonly=True)
            else:
                field("識別子", "org-unit-id", placeholder="例　sales-west")
            field(
                "種類",
                "org-kind",
                options=[("department", "部署"), ("project", "プロジェクト")],
                text=draft.get("kind", "department"),
            )
            field(
                "親部署",
                "org-parent",
                options=[("", "指定なし")]
                + [(r["id"], paths[r["id"]]) for r in units if r["kind"] == "department" and r != draft],
                text=draft.get("parent") or "",
            )
            with t.div(classes="btn-grouping"):
                btn("組織設定を保存", save_unit, primary=True)
                if draft:
                    btn("編集を取りやめる", edit_unit, None)

        if units:
            member = ctx.get("membership_draft") or {}
            with t.details(classes="box", open=bool(member)):
                t.summary("所属・役職・リーダーを設定")
                field(
                    "ユーザー",
                    "org-subject",
                    options=sorted(names.items(), key=lambda pair: pair[1]),
                    text=member.get("subject", ""),
                )
                if not directory_page or directory_page["next"]:
                    btn(
                        "ユーザーをさらに読み込む" if directory_page else "登録ユーザーを読み込む",
                        load_users,
                        directory_page.get("next", ""),
                    )
                field(
                    "所属先",
                    "org-membership-unit",
                    options=[(u["id"], paths[u["id"]]) for u in units],
                    text=member.get("unit_id", ""),
                )
                field("役職", "org-title", text=member.get("title", ""), placeholder="例　課長")
                field(
                    "管理権限",
                    "org-leader",
                    options=[("no", "メンバー"), ("yes", "リーダー")],
                    text="yes" if member.get("leader") else "no",
                )
                t.p(
                    "複数の部署やプロジェクトを兼務する場合は、所属先ごとに保存します。", classes="muted"
                )
                btn("所属を保存", save_membership, primary=True)

    t.h2("部署・プロジェクト一覧")
    if not units:
        t.p("表示できる部署・プロジェクトはありません。", classes="empty")
    usage = ctx.get("workspace_usage") or {}
    memberships = directory["memberships"]
    for unit in units:
        identifier = unit["id"]
        with t.article(classes="box"):
            t.h3(paths[identifier])
            label = "プロジェクト" if unit["kind"] == "project" else "部署"
            state = "利用停止中" if unit["stopped"] else "利用可能"
            parent = by_id.get(unit.get("parent"))
            while parent and state == "利用可能":
                if parent["stopped"]:
                    state = parent["name"] + "の設定により利用停止中"
                parent = by_id.get(parent.get("parent"))
            t.p(label + " · " + identifier + " · " + state)
            with t.div(classes="btn-grouping"):
                if admin:
                    btn("組織設定を編集", edit_unit, unit)
                if admin or identifier in leads:
                    btn("メンバーと利用状況", show_usage, unit)
                    btn("利用を再開" if unit["stopped"] else "利用を停止", toggle, unit)
            if admin or identifier in leads:
                credential_views.limit_view(ctx, field, btn, reload, kind="units", identifier=identifier)
            if admin:
                rows = [r for r in memberships if r["unit_id"] == identifier]
                if rows:
                    with t.details():
                        t.summary(f"直接の所属メンバー（{len(rows)}人）")
                        for row in rows:
                            with t.div(classes="compact-row"):
                                t.span(_membership(row, names, {}))
                                btn("所属を編集", edit_membership, row)
                                btn("所属を解除", remove_membership, row)
            if usage.get("unit_id") == identifier and (admin or identifier in leads):
                t.h3("利用状況")
                t.p(f"呼び出し {usage['calls']} 件　エラー {usage['errors']} 件")
                for title, key in (("プロジェクト別", "by_project"), ("API別", "by_api")):
                    with t.details(open=True):
                        t.summary(title)
                        if not usage[key]:
                            t.p("呼び出しの記録はありません。", classes="muted")
                        for item in usage[key]:
                            name = item.get("name") or item.get("project") or item["asset_id"]
                            t.p(f"{name}　{item['calls']} 件")
                with t.details(open=True):
                    t.summary("対象メンバー")
                    for row in usage["members"]:
                        t.p(_membership(row, names, paths))
                    if not usage["members"]:
                        t.p("登録されたメンバーはいません。", classes="muted")
