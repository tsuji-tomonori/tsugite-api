import json

import api_docs
import client
import operation_views
import product_views
from audit_navigation import trace_lookup
from js import document, window
from listing_data import load_listing, publication
from portal_labels import LABEL
from portal_navigation import go, load
from portal_ui import btn, ctx, field, value
from puepy import t
from pyodide.http import pyfetch
from screen_registry import Screen


async def save_policy(asset):
    data = {"visibility": value("policy-visibility")}
    for key in ("projects", "departments", "auto_departments", "delegates"):
        fields = document.querySelectorAll('input[name="policy-' + key + '"]:checked')
        data[key] = [str(fields.item(i).value) for i in range(fields.length)]
    data["auto_titles"] = [
        v.strip() for v in value("policy-titles").replace("、", ",").split(",") if v.strip()
    ]
    await client.api("/apis/" + asset["id"] + "/policy?revision=" + str(asset["revision"]), "PUT", data)
    await load()
    ctx["message"] = "公開範囲と承認ルールを保存しました"


def policy_form(asset):
    rules = ctx["policy"]
    tree = ctx["policy_directory"]["units"]
    with t.details(classes="box"):
        t.summary("公開範囲と承認ルール")
        field(
            "カタログの公開範囲",
            "policy-visibility",
            options=[("all", "全員"), ("restricted", "選択した所属だけ")],
            text=rules["visibility"],
        )
        for key, label, kind in (
            ("projects", "公開先プロジェクト", "project"),
            ("departments", "公開先部署", "department"),
            ("auto_departments", "自動承認する申請者の部署", "department"),
            ("delegates", "判断を委任する部署のリーダー", "department"),
        ):
            with t.fieldset():
                t.legend(label)
                for u in tree:
                    if u["kind"] == kind:
                        with t.label(classes="scope-choice"):
                            t.input(
                                type="checkbox",
                                name="policy-" + key,
                                value=u["id"],
                                checked=u["id"] in rules[key],
                            )
                            t.span(u["name"])
        field(
            "自動承認する役職（複数はカンマ区切り）",
            "policy-titles",
            text=", ".join(rules["auto_titles"]),
        )
        t.p(
            "部署は子孫部署を含みます。申請者の部署または役職が一致すれば自動承認し、それ以外は提供者か委任先のリーダーが判断します。"
        )
        btn("公開・承認条件を保存", save_policy, asset, primary=True)


async def delete_listing(asset):
    if window.confirm(asset["name"] + "を削除し、既存の利用権も終了しますか？"):
        await client.api("/apis/" + asset["id"] + "?revision=" + str(asset["revision"]), "DELETE")
        await go("inventory")
        ctx["message"] = "APIを削除しました"


async def apply(asset):
    await client.api(
        "/apis/" + asset["id"] + "/requests",
        "POST",
        {
            "project": value("project"),
            "personal": value("grant-kind") == "personal"
            or value("project") == ctx["me"]["personal_project"],
            "environment": value("environment"),
            "reason": value("reason"),
            **product_views.answers(asset, value("environment"), value),
        },
    )
    await go("mine")
    ctx["message"] = "利用申請を送信しました"


async def invoke(asset):
    env, project = value("trial-grant").split("/")
    path = value("trial-path")
    if not path.startswith("/") or "#" in path:
        raise ValueError("/ で始まる操作パスを指定してください")
    method = value("trial-method")
    options = {
        "method": method,
        "headers": {
            **client.screen_headers(),
            "Authorization": "Bearer " + str(client.store.getItem("access")),
            "Content-Type": "application/json",
        },
    }
    if method not in ("GET", "DELETE") and value("trial-body"):
        options["body"] = value("trial-body")
    url = client.prefix + "/invoke/" + asset["id"] + "/" + env + "/" + project + path
    result = await pyfetch(url, **options)
    ctx["trace"] = str(result.headers.get("x-request-id") or "")
    ctx["trial"] = f"HTTP {result.status}\n" + (await result.string())[:6000]


def detail_page():
    a = ctx["detail"]
    if not a:
        t.p("APIを読み込み中…")
        return
    t.h1(a["name"])
    t.p(a["summary"])
    t.p(a["owner"] + " · " + ("公開中" if a["published"] else "未掲載"), classes="muted")
    if a["owner"] in ctx["me"]["owners"]:
        btn(
            "掲載を取り下げる" if a["published"] else "公開する",
            publication,
            a,
            primary=not a["published"],
        )
        btn("内容を編集", go, "edit/" + a["id"])
        btn("APIを削除", delete_listing, a)
        policy_form(a)
        operation_views.provider_view(a, ctx, field, btn, load)
    with t.details(classes="box"):
        t.summary("OpenAPI定義を表示")
        t.pre(json.dumps(a["spec"], ensure_ascii=False, indent=2), classes="code")
    for row in ctx.get("rights", []):
        with t.div(classes="grant-status"):
            if row.get("subject"):
                t.small("個人の利用権")
            t.strong(
                row["project"] + " · " + LABEL[row["environment"]] + " · " + LABEL[row["status"]],
                classes="pill " + row["status"],
            )
            if row.get("decision_reason"):
                t.span("判断理由　" + row["decision_reason"])
    product_views.release_history(a)
    api_docs.view(a, ctx.get("rights", []), ctx.get("keys", []), subject=ctx["me"]["subject"])
    if a["published"]:
        with t.div(classes="box"):
            t.h2("利用申請")
            field(
                "利用プロジェクト",
                "project",
                options=[(p, p) for p in ctx["me"]["projects"]]
                + [(ctx["me"]["personal_project"], "個人ワークスペース")],
            )
            field(
                "申請対象",
                "grant-kind",
                options=[("project", "プロジェクト全員"), ("personal", "自分だけ")],
            )
            product_views.application_form(a, field)
            field("利用目的", "reason", textarea=True)
            btn("申請する", apply, a, primary=True)
    rights = [r for r in ctx.get("rights", []) if r["asset_id"] == a["id"] and r["status"] == "approved"]
    if rights:
        with t.div(classes="box"):
            t.h2("APIを呼び出す")
            field(
                "承認済みの環境とプロジェクト",
                "trial-grant",
                options=[
                    (
                        r["environment"] + "/" + r["project"],
                        LABEL[r["environment"]] + " · " + r["project"],
                    )
                    for r in rights
                ],
            )
            example = rights[0]
            root = f"{window.location.origin}{client.prefix}/invoke/{a['id']}/{example['environment']}/{example['project']}"
            t.p("呼び出し先　" + root, classes="code")
            field(
                "メソッド",
                "trial-method",
                options=[(m, m) for m in ("GET", "POST", "PUT", "PATCH", "DELETE")],
                text=next(
                    (
                        m.upper()
                        for m in next(iter(a["spec"]["paths"].values()))
                        if m in ("get", "post", "put", "patch", "delete")
                    ),
                    "GET",
                ),
            )
            field("操作パス", "trial-path", text=next(iter(a["spec"]["paths"])))
            field("リクエスト本文", "trial-body", textarea=True)
            btn("実行する", invoke, a, primary=True)
            if ctx["trial"]:
                t.pre(ctx["trial"], classes="code")
                if ctx["trace"]:
                    t.small("リクエストID　" + ctx["trace"], classes="mono")
                    btn("この実行の監査履歴", trace_lookup, ctx["trace"])


SCREENS = (Screen("api/", "APIの詳細", detail_page, load_listing, own_heading=True),)
