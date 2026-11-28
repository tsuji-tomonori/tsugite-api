"""利用申請に保存された承認順と判断履歴を表で表示する。"""

from __future__ import annotations

from typing import Any

from content.portal_labels import LABEL
from puepy import t

from components.list_layout import result_table
from components.product_views import step_label


def reviewer(step: str) -> str:
    """承認担当を表示し、名簿にない個別指定は担当種別と識別子で示す。"""
    label = step_label(step)
    if label == step:
        if step.startswith("person/"):
            return "指名ユーザー " + step.removeprefix("person/")
        if step.startswith("unit/"):
            return step.removeprefix("unit/") + "のリーダー"
    return label


def request_progress(row: dict[str, Any]) -> None:
    """申請一覧に状態を示し、展開すると段階別に担当と判断結果を示す。"""
    status = row["status"]
    evidence = row.get("application", {})
    steps = evidence.get("steps", [])
    decisions = evidence.get("decisions", [])
    t.strong(LABEL[status], classes=status)
    current = len(decisions)
    if status == "pending" and steps and current < len(steps):
        t.p(f"{current + 1}/{len(steps)}段階　{reviewer(steps[current])}")
    elif status == "pending" and evidence.get("route") == "legacy":
        t.p("提供者または委任先が審査")
    with t.details():
        t.summary("承認経路")
        if not steps:
            route = evidence.get("route")
            if route == "auto":
                t.p("自動承認（担当者による審査なし）")
            elif route == "legacy":
                t.p("商品共通の承認ルール")
                if status == "pending":
                    t.p("提供者または委任先の判断を待っています。")
            else:
                t.p("この申請には承認経路の記録がありません。")
            return
        with result_table("承認経路", ("段階", "承認担当", "状態", "判断者・理由")):
            for index, step in enumerate(steps):
                decision = decisions[index] if index < len(decisions) else {}
                waiting = status == "pending" and index == current
                with t.tr():
                    t.th(str(index + 1), scope="row")
                    t.td(reviewer(step))
                    with t.td():
                        if waiting:
                            t.strong("承認待ち", aria_current="step")
                        elif decision:
                            t.span("却下" if decision["action"] == "reject" else "承認済み")
                        else:
                            t.span("未到達" if index != current or status != "withdrawn" else "取下げ")
                    t.td(f"{decision['actor']}　{decision['reason']}" if decision else "—")
