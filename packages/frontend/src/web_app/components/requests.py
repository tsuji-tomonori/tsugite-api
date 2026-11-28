"""利用申請の状態と審査操作を表示する。"""

from __future__ import annotations

from typing import Any

from actions.requests import decide, save_guidelines
from content.portal_labels import ACTIONS, LABEL
from js import document
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx

from components import product_views
from components.controls import btn, field
from components.list_layout import result_table
from components.request_progress import request_progress


def rights_page(incoming: bool, rows: list[dict[str, Any]]) -> None:
    """申請の向きに応じて状態と判断欄を描画する。"""
    if not rows:
        t.p("申請はありません。", classes="muted")
        return
    with result_table(
        "届いた申請" if incoming else "自分の申請",
        ("API", "プロジェクト・環境・状態", "申請内容", "操作")
        if incoming
        else ("API", "プロジェクト・環境", "ステータス", "申請内容", "操作"),
    ):
        for row in rows:
            with t.tr():
                t.th(row.get("asset_name") or row["asset_id"], scope="row")
                context = f"{row['project']} · {LABEL[row['environment']]}"
                if incoming:
                    t.td(f"{context} · {LABEL[row['status']]}", classes=row["status"])
                else:
                    t.td(context)
                    with t.td():
                        request_progress(row)
                with t.td():
                    if row.get("applicant"):
                        t.p(
                            ("個人申請" if row.get("subject") else "プロジェクト申請")
                            + "　申請者 "
                            + row["applicant"]
                        )
                    t.p("利用目的　" + row["reason"])
                    if incoming and (stage := row.get("stage")):
                        t.p(product_views.step_label(stage) + "の承認待ち")
                    evidence = row.get("application", {})
                    for decision in evidence.get("decisions", []) if incoming else []:
                        t.p(
                            product_views.step_label(decision["stage"])
                            + " · "
                            + ACTIONS[decision["action"]]
                            + " · "
                            + decision["actor"]
                            + "　"
                            + decision["reason"]
                        )
                    if evidence.get("terms_accepted"):
                        with t.details():
                            t.summary("同意済みの利用規約")
                            t.p(evidence["terms"], classes="terms-text")
                    for label, answer in evidence.get("answers", {}).items():
                        t.p(label + "　" + answer)
                    if row.get("decision_reason"):
                        t.p("判断理由　" + row["decision_reason"], classes="decision")
                with t.td():
                    acts = (
                        {
                            "pending": [("承認", "approve"), ("却下", "reject")],
                            "approved": [("権限を取り消す", "revoke")],
                        }
                        if incoming
                        else {"pending": [("申請を取り下げる", "withdraw")]}
                    ).get(row["status"], [])
                    if acts:
                        field("判断・取下げの理由", "reason-" + row["id"])
                        with t.div(classes="btn-grouping"):
                            for title, op in acts:
                                btn(title, decide, row, op, primary=op == "approve")
                    if not incoming and row["status"] == "approved":
                        btn("APIを開く", go, "api/" + row["asset_id"])
                        btn("APIクライアントで開く", go, "console/" + row["asset_id"])


def inbox() -> None:
    """公開の審査と利用申請を表示する。"""
    if ctx["me"].get("admin"):
        policy = ctx.get("publication_policy", {})
        units = ctx.get("policy_directory", {}).get("units", [])

        def manage(event: Any) -> None:
            target = event.target
            if target.getAttribute("data-add") == "step":
                template = document.getElementById("publication-template").firstElementChild
                document.getElementById("publication-steps").appendChild(template.cloneNode(True))
            elif target.getAttribute("data-remove") == "step":
                target.closest(".approval-step").remove()

        with t.details(classes="box", on_click=manage):
            t.summary("提供ガイドラインと公開承認の設定")
            field(
                "提供ガイドライン",
                "publication-guidelines",
                textarea=True,
                text=policy.get("guidelines", ""),
            )
            t.p("上から順に承認を求めます。保存後に届く公開申請から適用します。")
            with t.div(id="publication-steps"):
                for step in policy.get("steps", ["admin"]):
                    product_views.step_row(step, units)
            with t.div(id="publication-template", hidden=True):
                product_views.step_row("admin", units)
            t.button("承認段階を追加", type="button", classes="btn", data_add="step")
            btn("提供ガイドラインと承認順を保存", save_guidelines)
    t.h2("公開申請")
    for asset in ctx.get("publication_requests", []):
        t.a(asset["name"], href="#/api/" + asset["id"])
    if not ctx.get("publication_requests"):
        t.p("現在、判断を待っている公開申請はありません。")
    t.h2("利用申請")
    rights_page(True, ctx["rows"])
