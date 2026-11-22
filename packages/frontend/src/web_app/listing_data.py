import asyncio
from urllib.parse import quote, urlencode

import client
from portal_navigation import load
from portal_ui import ctx


async def publication(asset):
    await client.api(
        "/apis/" + asset["id"] + "/publication?published=" + str(not asset["published"]).lower(), "PUT"
    )
    await load()
    ctx["message"] = "掲載状態を更新しました"


async def load_listing(page):
    if (ctx["detail"] or {}).get("id") != page.split("/", 1)[1]:
        ctx.update(trial="", trace="")
    ctx["detail"] = None
    ctx["detail"] = await client.api("/apis/" + quote(page.split("/", 1)[1], safe=""))
    ctx["keys"] = await client.api("/keys")
    if ctx["detail"]["owner"] in ctx["me"]["owners"]:
        ctx["op_policy"] = await client.api("/apis/" + ctx["detail"]["id"] + "/operation-policy")
        ctx["policy"], ctx["policy_directory"] = await asyncio.gather(
            client.api("/apis/" + ctx["detail"]["id"] + "/policy"), client.api("/workspace")
        )
    ctx["rights"] = await client.api("/requests?" + urlencode({"asset_id": ctx["detail"]["id"]}))
