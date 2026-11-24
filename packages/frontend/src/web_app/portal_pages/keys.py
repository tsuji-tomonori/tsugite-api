import asyncio
from urllib.parse import quote

import client
import credential_views
import guide_examples as example
from js import document, window
from list_layout import disclosure, result_table
from portal_navigation import load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def load_keys(_page):
    ctx["workspace"] = await client.api("/workspace")
    ctx["keys"], ctx["key_assets"] = await asyncio.gather(client.api("/keys"), client.api("/key-assets"))


def _show_scope_options(event):
    document.getElementById("key-asset-list").hidden = str(event.target.value) != "selected"


def key_form(projects, assets, create_key, *, expanded=False):
    with disclosure("APIキーを作成", expanded=expanded):
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


def keys_view():
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
        restricted = value("key-scope") == "selected"
        selected = [a["id"] for a in assets if document.getElementById("key-asset-" + a["id"]).checked]
        if restricted and not selected:
            raise client.InputError("このキーで呼び出すAPIを選んでください")
        kind = value("key-kind")
        project = value("key-project")
        if project == personal and kind == "shared":
            raise client.InputError("本人の利用申請には本人専用キーを選んでください")
        result = await client.api(
            "/keys",
            "POST",
            {
                "name": value("key-name"),
                "kind": kind,
                "project": project,
                "api_ids": selected if restricted else [],
            },
        )
        ctx["issued_key"] = {"subject": me["subject"], "secret": result["secret"]}
        await load()

    async def hide_secret():
        ctx.pop("issued_key", None)

    async def copy_secret():
        await window.navigator.clipboard.writeText(ctx["issued_key"]["secret"])
        ctx["message"] = "キーをコピーしました"

    async def revoke_key(row):
        if window.confirm(row["name"] + " を失効し、このキーを使った呼び出しを停止しますか？"):
            await client.api("/keys/" + quote(row["id"], safe=""), "DELETE")
            ctx.pop("issued_key", None)
            await load()
            ctx["message"] = "キーを失効しました"

    credential_views.credentials_view(ctx, field, btn, load, projects)
    legacy = [k for k in ctx["keys"] if k.get("mode") not in credential_views.MODES]
    secret = ctx.get("issued_key") or {}
    if secret.get("subject") == me["subject"] and not secret.get("mode"):
        with t.section(classes="box"):
            t.h2("発行したAPIキー")
            t.p("キー全文はこの画面で一度だけ表示します。安全な保管先にコピーしてください。")
            t.code(secret["secret"], classes="code", id="issued-secret")
            with t.div(classes="btn-grouping"):
                btn("キーをコピー", copy_secret, primary=True)
                btn("表示を閉じる", hide_secret)
    with t.div(classes="list-tools"):
        t.h2("従来のAPIキー")
        if projects:
            key_form(projects, assets, create_key)
    if not legacy:
        t.p("表示できるキーはありません。", classes="empty")
        return
    with result_table("APIキー一覧", ("名前", "所有者・状態", "対象API・キーID", "操作")):
        for row in legacy:
            with t.tr():
                t.th(row["name"], scope="row")
                kind = "本人専用" if row["kind"] == "personal" else "プロジェクト共有"
                project_name = (
                    "本人の利用申請"
                    if row["project"] == personal
                    else names.get(row["project"], row["project"])
                )
                t.td(kind + " · " + project_name + " · " + ("失効済み" if row["revoked"] else "有効"))
                with t.td():
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
                with t.td():
                    if not row["revoked"]:
                        with t.details():
                            t.summary("外部からの呼び出し方")
                            if row["kind"] == "shared":
                                t.p("リクエストの認証ヘッダーに、発行時に保存した共有キーを設定します。")
                                t.pre("Authorization: Bearer <共有キー>", classes="code")
                            else:
                                t.p(
                                    "発行した本人のアクセストークンと、保存した本人専用キーを両方設定します。"
                                )
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


SCREENS = (
    Screen(
        "keys",
        "APIキー",
        keys_view,
        load_keys,
        group="ワークスペース",
        order=30,
        examples={
            "keys": lambda: key_form(example.PROJECTS, [example.ASSET], None, expanded=True),
            "credential": lambda: credential_views.render_form(
                {"me": example.USER}, example.PROJECT["id"], example.OPTIONS, field, btn, load
            ),
            "rotate": lambda: credential_views.credentials_view(
                {"me": example.USER, "workspace": {"admin": False, "leads": []}, "keys": [example.KEY]},
                field,
                btn,
                load,
                [],
            ),
        },
    ),
)
