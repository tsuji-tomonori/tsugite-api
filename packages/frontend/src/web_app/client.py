import json
from urllib.parse import parse_qs, quote, urlencode

from js import window
from log_record import SCREENS, log_record
from pyodide.http import pyfetch

store = window.sessionStorage
prefix = "/api"


def invocation_path(asset, environment, project):
    segments = (asset.get("slug") or asset["id"], environment, project)
    return prefix + "/invoke/" + "/".join(quote(part, safe="") for part in segments)


class InputError(ValueError):
    """ポータルの入力または認証の条件を満たさない。"""


class ResponseStatusError(Exception):
    """アプリに到達する前にHTTPエラー応答を受け取った。"""


class ResponseError(ValueError):
    """APIの応答に対応するイベントはサーバー側で記録する。"""


def viewer():
    return None


def screen():
    if not viewer():
        return "login"
    page = str(window.location.hash).lstrip("#/").partition("/")[0] or "home"
    return page if page in SCREENS else None


def report(exc, operation, *, route=None, status=None, method=None, request_id=None):
    if isinstance(exc, ResponseError):
        return
    console = getattr(window, "console", None)
    if console is None:
        return
    user_error = (
        (status is not None and 400 <= status < 500)
        or isinstance(exc, InputError)
        or getattr(exc, "user_error", False)
    )
    entry = log_record(
        "ui.error",
        source="browser",
        screen=screen(),
        actor_id=viewer(),
        user_error=user_error,
        failed=not user_error,
        reason=type(exc).__name__,
        operation=operation,
        route=route,
        status=status,
        method=method,
        request_id=request_id,
        asset_id=str(window.location.hash).lstrip("#/").partition("/")[2]
        if screen() in {"api", "apply", "edit"}
        else None,
    )
    sink = console.warn if entry["level"] == "WARN" else console.error
    sink(json.dumps(entry, ensure_ascii=False))


def screen_headers():
    page = screen()
    return {"X-Tsugite-Screen": page} if page else {}


async def api(path, method="GET", data=None):
    headers = screen_headers()
    token = store.getItem("access")
    if token:
        headers["Authorization"] = "Bearer " + str(token)
    opts = {"method": method, "headers": headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
        opts["body"] = json.dumps(data)
    # The first segment comes from the portal call site; all dynamic IDs follow it.
    endpoint = "/api/" + path.split("?", 1)[0].strip("/").split("/", 1)[0]
    try:
        result = await pyfetch(prefix + path, **opts)
    except Exception as exc:
        report(exc, "fetch", route=endpoint, method=method)
        raise ResponseError("APIから応答を取得できませんでした") from exc
    try:
        value = await result.json()
    except (ValueError, TypeError) as exc:
        if result.ok:
            report(
                exc,
                "decode_response",
                route=endpoint,
                method=method,
                request_id=result.headers.get("x-request-id"),
            )
            raise ResponseError("APIの応答を読み取れませんでした") from exc
        value = {}
    if not result.ok:
        if result.status == 401:
            store.removeItem("access")
        if not result.headers.get("x-request-id"):
            # An edge service may reject the request before the application sees it.
            report(ResponseStatusError(), "fetch", route=endpoint, method=method, status=result.status)
        detail = value.get("detail") if isinstance(value, dict) else None
        if isinstance(detail, list):
            detail = "入力内容を確認してください"
        raise ResponseError(f"{detail or '処理できませんでした'} ({result.status})")
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
        raise InputError("ログインをやり直してください")
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
