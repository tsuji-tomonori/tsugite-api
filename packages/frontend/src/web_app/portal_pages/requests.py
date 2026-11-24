import client
import guide_examples as example
import product_views
from list_layout import result_table
from portal_labels import ACTIONS, LABEL
from portal_navigation import go, load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def decide(row, decision):
    await client.api(
        "/requests/" + row["id"],
        "POST",
        {"action": decision, "revision": row["revision"], "reason": value("reason-" + row["id"])},
    )
    await load()
    ctx["message"] = "申請状態を更新しました"


def rights_page(incoming, rows):
    if not rows:
        t.p("申請はありません。", classes="muted")
        return
    with result_table(
        "届いた申請" if incoming else "自分の申請",
        ("API", "プロジェクト・環境・状態", "申請内容", "操作"),
    ):
        for row in rows:
            with t.tr():
                t.th(row.get("asset_name") or row["asset_id"], scope="row")
                t.td(
                    f"{row['project']} · {LABEL[row['environment']]} · {LABEL[row['status']]}",
                    classes=row["status"],
                )
                with t.td():
                    if row.get("applicant"):
                        t.p(
                            ("個人申請" if row.get("subject") else "プロジェクト申請")
                            + "　申請者 "
                            + row["applicant"]
                        )
                    t.p("利用目的　" + row["reason"])
                    stage = {"department": "所属部署の承認待ち", "provider": "提供者の承認待ち"}.get(
                        row.get("stage")
                    )
                    if row.get("stage", "") and row["stage"].startswith("unit/"):
                        stage = row["stage"][5:] + " 部署の承認待ち"
                    if stage:
                        t.p(stage)
                    evidence = row.get("application", {})
                    for decision in evidence.get("decisions", []):
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


async def load_requests(page):
    ctx["rows"] = await client.api("/requests?incoming=" + str(page == "inbox").lower())


SCREENS = (
    Screen(
        "mine",
        "自分の申請",
        lambda: rights_page(False, ctx["rows"]),
        load_requests,
        examples={"status": lambda: rights_page(False, [example.REQUEST])},
        group="ワークスペース",
        order=40,
        description="プロジェクトの申請状況と、承認されたAPIを確認できます。",
    ),
    Screen(
        "inbox",
        "届いた申請",
        lambda: rights_page(True, ctx["rows"]),
        load_requests,
        examples={"review": lambda: rights_page(True, [example.REQUEST])},
        group="提供者メニュー",
        order=120,
        visible=lambda user: bool(user["owners"] or user["leads"]),
        description="利用目的と環境を確認し、チームに届いた申請を判断します。",
    ),
)
