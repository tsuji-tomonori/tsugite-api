import json
from urllib.parse import parse_qs, urlencode

from js import window
from pyodide.http import pyfetch

store = window.sessionStorage
prefix = "/api"


async def api(path, method="GET", data=None):
    headers = {}
    token = store.getItem("access")
    if token:
        headers["Authorization"] = "Bearer " + str(token)
    opts = {"method": method, "headers": headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
        opts["body"] = json.dumps(data)
    result = await pyfetch(prefix + path, **opts)
    value = await result.json()
    if not result.ok:
        if result.status == 401:
            store.removeItem("access")
        detail = value.get("detail")
        if isinstance(detail, list):
            detail = "入力内容を確認してください"
        raise ValueError(f"{detail or '処理できませんでした'} ({result.status})")
    return value


async def callback(cfg):
    params = parse_qs(str(window.location.search).lstrip("?"))
    if "code" not in params and "error" not in params:
        return
    window.history.replaceState(None, "", str(window.location.pathname))
    state = store.getItem("oauth_state")
    verifier = store.getItem("pkce")
    store.removeItem("oauth_state")
    store.removeItem("pkce")
    if not state or params.get("state") != [str(state)] or "code" not in params:
        raise ValueError("ログインをやり直してください")
    payload = urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": cfg["client_id"],
            "code": params["code"][0],
            "redirect_uri": str(window.location.origin) + "/",
            "code_verifier": str(verifier),
        }
    )
    result = await pyfetch(
        cfg["domain"] + "/oauth2/token",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=payload,
    )
    if not result.ok:
        raise ValueError("ログインをやり直してください")
    store.setItem("access", (await result.json())["access_token"])
