"""API商品詳細の公開設定と仕様を表示する。"""

from __future__ import annotations

import json
from typing import Any

from actions.listing_data import publication, review_publication
from actions.listing_detail import change_suspension, delete_listing, save_policy
from content.portal_labels import LABEL
from js import window
from puepy import t
from routing.portal_navigation import go, load
from runtime.portal_download import save_blob
from runtime.portal_ui import ctx

from components import api_docs, operation_views, product_views
from components.controls import btn, field


def policy_form(
    asset: dict[str, Any],
    rules: dict[str, Any],
    tree: list[dict[str, Any]],
    *,
    expanded: bool = False,
    fields: tuple[()] | list[dict[str, Any]] = (),
) -> None:
    """公開範囲の編集欄を描画する。"""
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
        values = {u["id"]: u for u in tree}
        field_labels = {f["key"]: f["label"] for f in fields if not f["builtin"] and f["public_values"]}
        selected = set(rules.get("metadata_values", []))
        choices = selected | {key for key, u in values.items() if u["kind"] in field_labels}
        if choices:
            with t.fieldset():
                t.legend("公開先のメタデータ（いずれかの値に所属）")
                for key in sorted(choices):
                    unit = values.get(key, {})
                    with t.label(classes="scope-choice"):
                        t.input(
                            type="checkbox",
                            name="policy-metadata_values",
                            value=key,
                            checked=key in selected,
                        )
                        t.span(
                            " / ".join(
                                filter(None, [field_labels.get(unit.get("kind")), unit.get("name", key)])
                            )
                        )
        field(
            "自動承認する役職（複数はカンマ区切り）",
            "policy-titles",
            text=", ".join(rules["auto_titles"]),
        )
        t.p(
            "部署は子孫部署を含みます。申請者の部署または役職が一致すれば自動承認し、それ以外は提供者か委任先のリーダーが判断します。"
        )
        btn("公開・承認条件を保存", save_policy, asset, primary=True)


def download_spec(asset: dict[str, Any]) -> None:
    """商品のOpenAPI定義を保存する。"""
    parts = window.Array.new()
    parts.push(json.dumps(asset["spec"], ensure_ascii=False, indent=2))
    save_blob(window.Blob.new(parts), asset["name"] + ".openapi.json")


def publication_actions(a: dict[str, Any]) -> None:
    """公開状態に応じた管理操作を表示する。"""
    with t.div(classes="btn-grouping"):
        btn(
            "掲載を取り下げる"
            if a["published"]
            else ("公開申請を取り下げる" if a.get("publication_stage") else "公開申請する"),
            publication,
            a,
            primary=not a["published"],
        )
        btn("内容を編集", go, "edit/" + a["id"])
        btn("APIを削除", delete_listing, a)


def detail_page() -> None:
    """商品情報・仕様・操作権限を組み立てる。"""
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
    t.p("公開責任者　" + (a.get("responsible_label") or a.get("responsible") or a["owner"]))
    if stage := a.get("publication_stage"):
        t.p("公開承認待ち　" + product_views.step_label(stage))
    if a.get("can_review_publication"):
        t.p(a.get("publication_guidelines", ""), classes="terms-text")
        field("公開判断の理由", "publication-reason", required=True)
        btn("公開申請を承認", review_publication, a, True, primary=True)
        btn("公開申請を却下", review_publication, a, False)
    if a["owner"] in ctx["me"]["owners"]:
        publication_actions(a)
        policy_form(
            a,
            ctx["policy"],
            ctx["policy_directory"]["units"],
            fields=ctx["policy_directory"].get("metadata_fields", []),
        )
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
