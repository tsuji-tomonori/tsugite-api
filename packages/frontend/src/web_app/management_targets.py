import client
from portal_labels import LABEL
from portal_ui import ctx


def target_options():
    return [
        (r["id"], f"{r['name']} · {r['project']} · {LABEL[r['environment']]}")
        for r in ctx.get("targets", [])
    ]


async def load_targets():
    ctx["targets"] = (
        await client.api("/management-targets") if ctx["me"]["owners"] or ctx["me"]["admin"] else []
    )
