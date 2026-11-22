"""Provider controls for a person's effective API operations."""

from urllib.parse import quote

import client
import credential_views
from js import document
from puepy import t


def provider_view(asset, ctx, field, btn, load):
    credential_views.limit_view(ctx, field, btn, load, kind="apis", identifier=asset["id"])
    policy = ctx["op_policy"]
    operations = policy["operations"]
    permissions = policy["permissions"]
    names = {m["subject"]: m["username"] for m in policy["members"]}
    for subject in permissions:
        names.setdefault(subject, subject)
    draft = ctx.get("edit_operations", {})
    subject = draft.get("subject") if draft.get("api") == asset["id"] else ""
    if subject not in names:
        subject = ""

    async def choose():
        chosen = str(document.getElementById("op-person").value)
        ctx["edit_operations"] = {"api": asset["id"], "subject": chosen}

    def select_operations(read_only):
        def update(event):
            for n, op in enumerate(operations):
                method = op.partition(" ")[0]
                document.getElementById(f"op-allow-{n}").checked = (
                    method in {"GET", "HEAD", "OPTIONS"} if read_only else False
                )

        return update

    async def save_selection(inherit=False):
        if str(document.getElementById("op-person").value) != subject:
            raise ValueError("利用者を選び直した場合は「権限を表示」を押してください")
        values = (
            None
            if inherit
            else [
                op for n, op in enumerate(operations) if document.getElementById(f"op-allow-{n}").checked
            ]
        )
        await client.api(
            "/apis/" + quote(asset["id"], safe="") + "/operation-policy",
            "PUT",
            {"subject": subject, "operations": values},
        )
        await load()
        ctx["message"] = names[subject] + " の操作権限を保存しました"

    with t.details(classes="box", open=bool(subject)):
        t.summary("利用者ごとの操作権限")
        if not names:
            t.p("対象となる利用者がいません。")
            return
        options = sorted(names.items(), key=lambda pair: (pair[1], pair[0]))
        field("対象の利用者", "op-person", options=options, text=subject or options[0][0])
        btn("権限を表示", choose)
        if not subject:
            return
        with t.section():
            t.h3(names[subject] + " の操作")
            allowed = permissions.get(subject)
            current = (
                "APIの利用権と認証情報の範囲を継承"
                if allowed is None
                else f"個別設定 · {len(allowed)} 操作を許可"
            )
            t.p("現在の設定　" + current)
            if operations:
                with t.fieldset():
                    t.legend("許可する操作")
                    with t.div(classes="btn-grouping"):
                        t.button(
                            "参照だけを選ぶ",
                            type="button",
                            classes="btn btn-outline-secondary",
                            on_click=select_operations(True),
                        )
                        t.button(
                            "すべて外す",
                            type="button",
                            classes="btn btn-outline-secondary",
                            on_click=select_operations(False),
                        )
                    for n, op in enumerate(operations):
                        credential_views.checkbox(
                            f"op-allow-{n}", op, selected=allowed is None or op in allowed
                        )
                t.p("選択をすべて外して保存すると、この利用者の呼び出しを停止します。", classes="muted")
                btn("選んだ操作を保存", save_selection, primary=True)
            if allowed is not None:
                btn("個別設定を解除して継承", save_selection, True)
