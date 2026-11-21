"""Organization directory, leader usage views, and API key issuance for the Python portal."""

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


def _show_scope_options(event):
    document.getElementById("key-asset-list").hidden = str(event.target.value) != "selected"


def keys_view(ctx, field, btn, reload):
    me = ctx["me"]
    directory = ctx["workspace"]
    names = {u["id"]: u["name"] for u in directory["units"]}
    projects = [(p, names.get(p, p)) for p in me["projects"]]
    personal = me.get("personal_project")
    if personal and personal not in {p for p, _ in projects}:
        projects.append((personal, "本人の利用申請"))
    assets = ctx.get("key_assets", [])
    asset_names = {a["id"]: a["name"] for a in assets}

    async def create_key():
        restricted = _value("key-scope") == "selected"
        selected = [a["id"] for a in assets if document.getElementById("key-asset-" + a["id"]).checked]
        if restricted and not selected:
            raise ValueError("このキーで呼び出すAPIを選んでください")
        kind = _value("key-kind")
        project = _value("key-project")
        if project == personal and kind == "shared":
            raise ValueError("本人の利用申請には本人専用キーを選んでください")
        result = await client.api(
            "/keys",
            "POST",
            {
                "name": _value("key-name"),
                "kind": kind,
                "project": project,
                "api_ids": selected if restricted else [],
            },
        )
        ctx["issued_key"] = {"subject": me["subject"], "secret": result["secret"]}
        await reload()

    async def hide_secret():
        ctx.pop("issued_key", None)

    async def copy_secret():
        await window.navigator.clipboard.writeText(ctx["issued_key"]["secret"])
        ctx["message"] = "キーをコピーしました"

    async def revoke_key(row):
        if window.confirm(row["name"] + " を失効し、このキーを使った呼び出しを停止しますか？"):
            await client.api("/keys/" + quote(row["id"], safe=""), "DELETE")
            ctx.pop("issued_key", None)
            await reload()
            ctx["message"] = "キーを失効しました"

    credential_views.credentials_view(ctx, field, btn, reload, projects)
    legacy = [k for k in ctx["keys"] if k.get("mode") not in credential_views.MODES]
    t.h2("従来のAPIキー")
    secret = ctx.get("issued_key") or {}
    if secret.get("subject") == me["subject"] and not secret.get("mode"):
        with t.section(classes="box"):
            t.h2("発行したAPIキー")
            t.p("キー全文はこの画面で一度だけ表示します。安全な保管先にコピーしてください。")
            t.code(secret["secret"], classes="code", id="issued-secret")
            with t.div(classes="btn-grouping"):
                btn("キーをコピー", copy_secret, primary=True)
                btn("表示を閉じる", hide_secret)
    if projects:
        with t.details(classes="box"):
            t.summary("APIキーを作成")
            field("キー名", "key-name", placeholder="例　棚卸バッチ")
            field("プロジェクト", "key-project", options=projects)
            field(
                "キーの種類",
                "key-kind",
                options=[("personal", "本人専用"), ("shared", "プロジェクト共有")],
            )
            with t.label(classes="field"):
                t.span("APIの範囲", id="key-scope-label")
                with t.select(
                    id="key-scope",
                    aria_labelledby="key-scope-label",
                    classes="form-select",
                    on_change=_show_scope_options,
                ):
                    t.option("利用を承認されたすべてのAPI", value="all")
                    t.option("指定したAPIのみ", value="selected")
            with t.div(id="key-asset-list", hidden=True):
                with t.details():
                    t.summary("対象APIを選ぶ")
                    for asset in assets:
                        with t.label(classes="compact-row"):
                            t.input(type="checkbox", id="key-asset-" + asset["id"])
                            t.span(asset["name"])
                    if not assets:
                        t.p("選択できるAPIはありません。", classes="muted")
            btn("キーを発行", create_key, primary=True)
    t.h2("APIキー一覧")
    if not legacy:
        t.p("表示できるキーはありません。", classes="empty")
    for row in legacy:
        with t.article(classes="box"):
            t.h3(row["name"])
            kind = "本人専用" if row["kind"] == "personal" else "プロジェクト共有"
            project_name = (
                "本人の利用申請"
                if row["project"] == personal
                else names.get(row["project"], row["project"])
            )
            t.p(kind + " · " + project_name + " · " + ("失効済み" if row["revoked"] else "有効"))
            scopes = row["api_ids"]
            t.p(
                "対象API　"
                + (
                    "、".join(asset_names.get(i, i) for i in scopes)
                    if scopes
                    else "利用を承認されたすべてのAPI"
                )
            )
            t.small("キーID　" + row["id"], classes="mono")
            if not row["revoked"]:
                with t.details():
                    t.summary("外部からの呼び出し方")
                    if row["kind"] == "shared":
                        t.p("リクエストの認証ヘッダーに、発行時に保存した共有キーを設定します。")
                        t.pre("Authorization: Bearer <共有キー>", classes="code")
                    else:
                        t.p("発行した本人のアクセストークンと、保存した本人専用キーを両方設定します。")
                        t.pre(
                            "Authorization: Bearer <本人のアクセストークン>\nX-API-Key: <本人専用キー>",
                            classes="code",
                        )
                    t.p("ポータルから試す場合は、API詳細のAPI Docsでこのキーを選びます。")

            can_revoke = (
                directory["admin"]
                or row["creator"] == me["subject"]
                or row["kind"] == "shared"
                and row["project"] in directory["leads"]
            )
            if not row["revoked"] and can_revoke:
                with t.div(classes="btn-grouping"):
                    btn("キーを失効", revoke_key, row)
