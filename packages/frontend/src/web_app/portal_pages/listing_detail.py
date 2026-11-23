import json

import api_docs
import client
import guide_examples as example
import operation_views
import product_views
from js import document, window
from listing_data import load_listing, publication
from portal_download import save_blob
from portal_labels import LABEL
from portal_navigation import go, load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def change_suspension(asset):
    suspended = not asset["suspended"]
    action = "一時停止" if suspended else "再開"
    if window.confirm(asset["name"] + "への全環境のアクセスを" + action + "しますか？"):
        await client.api(
            "/apis/" + asset["id"] + "/suspension?suspended=" + str(suspended).lower(), "PUT"
        )
        await load()
        ctx["message"] = "APIへのアクセスを" + action + "しました"


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


def policy_form(asset, rules, tree, *, expanded=False):
    with t.details(classes="box", open=expanded):
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


def download_spec(asset):
    parts = window.Array.new()
    parts.push(json.dumps(asset["spec"], ensure_ascii=False, indent=2))
    save_blob(window.Blob.new(parts), asset["name"] + ".openapi.json")


def publication_actions(a):
    with t.div(classes="btn-grouping"):
        btn(
            "掲載を取り下げる" if a["published"] else "公開する",
            publication,
            a,
            primary=not a["published"],
        )
        btn("内容を編集", go, "edit/" + a["id"])
        btn("APIを削除", delete_listing, a)


def detail_page():
    a = ctx["detail"]
    if not a:
        t.p("APIを読み込み中…")
        return
    t.h1(a["name"])
    t.p(a["summary"])
    if ctx["me"]["admin"]:
        btn(
            "APIへのアクセスを再開" if a["suspended"] else "APIへのアクセスを一時停止",
            change_suspension,
            a,
        )
    t.p(a["owner"] + " · " + ("公開中" if a["published"] else "未掲載"), classes="muted")
    if a["owner"] in ctx["me"]["owners"]:
        publication_actions(a)
        policy_form(a, ctx["policy"], ctx["policy_directory"]["units"])
        operation_views.provider_view(a, ctx, field, btn, load)
    with t.div(classes="btn-grouping docs-actions"):
        if a["published"]:
            t.a("利用申請へ進む", href="#/apply/" + a["id"], classes="btn btn-primary")
        t.button(
            "OpenAPI定義をダウンロード（JSON）",
            type="button",
            classes="btn",
            on_click=lambda event: download_spec(a),
        )
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
    api_docs.view(
        a,
        ctx.get("rights", []),
        ctx.get("keys", []),
        subject=ctx["me"]["subject"],
        personal_project=ctx["me"]["personal_project"],
    )


SCREENS = (
    Screen(
        "api/",
        "APIの詳細",
        detail_page,
        load_listing,
        own_heading=True,
        examples={
            "edit": lambda: publication_actions(example.ASSET),
            "visibility": lambda: policy_form(
                example.ASSET, example.POLICY, [example.PROJECT], expanded=True
            ),
            "operations": lambda: operation_views.provider_view(
                example.ASSET, example.OPERATIONS, field, btn, load
            ),
            "invoke": lambda: api_docs.view(
                example.ASSET,
                [{**example.REQUEST, "status": "approved"}],
                [example.KEY],
                subject=example.USER["subject"],
                personal_project=example.USER["personal_project"],
            ),
        },
    ),
)
