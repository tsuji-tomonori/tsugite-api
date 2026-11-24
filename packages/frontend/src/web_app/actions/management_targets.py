# 通知とアラートの対象を共有する。
from __future__ import annotations

from apis import activity as activity_api
from content.portal_labels import LABEL
from runtime.portal_ui import ctx


def target_options() -> list[tuple[str, str]]:
    """識別子と表示名の選択肢を作る。"""
    return [
        (r["id"], f"{r['name']} · {r.get('project_label', r['project'])} · {LABEL[r['environment']]}")
        for r in ctx.get("targets", [])
    ]


async def load_targets() -> None:
    """管理できる申請を取得する。"""
    ctx["targets"] = await activity_api.targets() if ctx["me"]["owners"] or ctx["me"]["admin"] else []
