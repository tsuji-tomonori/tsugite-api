# アラートの画面と操作を定義する。
import client
import guide_examples as example
from list_layout import disclosure, result_table
from management_targets import load_targets, target_options
from portal_labels import LABEL
from portal_navigation import load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def save_alert():
    asset, project, env = value("alert-target").split("/")
    await client.api(
        "/alerts",
        "PUT",
        {
            "asset_id": asset,
            "project": project,
            "environment": env,
            "threshold": int(value("alert-threshold")),
            "minutes": int(value("alert-minutes")),
            "stop": value("alert-action") == "stop",
            "enabled": value("alert-action") != "off",
        },
    )
    await load()
    ctx["message"] = "アラート設定を保存しました"


def rule_form(targets, *, expanded=False):
    with disclosure("利用件数のルール", expanded=expanded):
        field("対象の利用申請", "alert-target", options=targets)
        field(
            "集計期間",
            "alert-minutes",
            options=[(str(n), str(n) + "分") for n in (1, 5, 15, 60, 1440)],
        )
        field("しきい値（件）", "alert-threshold", text="100")
        field(
            "到達時の動作",
            "alert-action",
            options=[
                ("notify", "通知する"),
                ("stop", "通知し、次の期間まで停止"),
                ("off", "ルールを無効にする"),
            ],
        )
        t.p(
            "UTCの固定区間で集計します。しきい値に達した呼び出しを通し、停止設定では次の呼び出しから429を返します。設定を保存するとカウンターをリセットします。"
        )
        btn("ルールを保存", save_alert, primary=True)


def alerts_view():
    targets = target_options()
    if targets:
        with t.div(classes="list-tools"):
            rule_form(targets)
    if not ctx["rules"]:
        t.p("設定済みのルールはありません。", classes="empty")
        return
    with result_table(
        "設定済みのルール",
        ("API", "プロジェクト", "環境", "集計期間", "しきい値", "現在の件数", "到達時の動作"),
    ):
        for r in ctx["rules"]:
            with t.tr():
                t.th(r["name"], scope="row")
                t.td(r["project"])
                t.td(LABEL[r["environment"]])
                t.td(f"{r['minutes']}分")
                t.td(f"{r['threshold']}件")
                t.td(f"{r['calls']}件")
                t.td("無効" if not r["enabled"] else "通知と停止" if r["stop"] else "通知")


async def load_alerts(_page):
    await load_targets()
    ctx["rules"] = await client.api("/alerts")


SCREENS = (
    Screen(
        "alerts",
        "アラート",
        alerts_view,
        load_alerts,
        group="ガバナンス",
        order=150,
        examples={"alerts": lambda: rule_form(example.TARGETS, expanded=True)},
    ),
)
