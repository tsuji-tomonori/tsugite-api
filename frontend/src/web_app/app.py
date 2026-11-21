import asyncio
import json
from urllib.parse import quote, urlencode

import client
from js import document, window
from puepy import Application, Page, t
from pyodide.ffi.wrappers import add_event_listener
from pyodide.http import pyfetch

app = Application()
ctx = {
    "config": None,
    "me": None,
    "rows": [],
    "detail": None,
    "message": "",
    "error": False,
    "busy": False,
    "query": "",
    "trial": "",
}
LABEL = {
    "pending": "承認待ち",
    "approved": "利用中",
    "rejected": "却下",
    "revoked": "取消済み",
    "withdrawn": "取下げ済み",
    "sandbox": "検証",
    "production": "本番",
}
SAMPLE = {
    "openapi": "3.0.3",
    "info": {"title": "在庫照会", "version": "1.0.0"},
    "paths": {
        "/items": {"get": {"summary": "在庫を照会", "responses": {"200": {"description": "照会結果"}}}}
    },
}
PAGES = {
    "catalog": "APIカタログ",
    "mine": "自分の申請",
    "inventory": "提供するAPI",
    "inbox": "届いた申請",
    "audit": "監査履歴",
}


def value(name):
    return str(document.getElementById(name).value).strip()


def route():
    return str(window.location.hash).lstrip("#/") or "catalog"


def render():
    app.mount("#app")


def action(fn, *args):
    def clicked(event):
        event.preventDefault()
        asyncio.ensure_future(run(fn, *args))

    return clicked


async def run(fn, *args):
    if ctx["busy"]:
        return
    ctx.update(busy=True, message="", error=False)
    try:
        await fn(*args)
    except Exception as exc:
        ctx.update(message=str(exc), error=True)
        if not client.store.getItem("access"):
            ctx["me"] = None
    finally:
        ctx["busy"] = False
        render()


def btn(label, fn, *args, primary=False):
    return t.button(
        label,
        type="button",
        classes="btn btn-primary" if primary else "btn btn-outline-secondary",
        on_click=action(fn, *args),
    )


def field(label, name, options=None, textarea=False, text="", placeholder=""):
    with t.label(classes="field"):
        t.span(label)
        if options is not None:
            with t.select(id=name, classes="form-select"):
                for key, title in options:
                    t.option(title, value=key)
        elif textarea:
            t.textarea(text, id=name, classes="form-control", placeholder=placeholder)
        else:
            t.input(id=name, value=text, classes="form-control", placeholder=placeholder)


async def load():
    if not ctx["me"]:
        return
    page = route()
    if page.startswith("api/"):
        ctx["detail"] = await client.api("/apis/" + quote(page[4:], safe=""))
        ctx["rights"] = await client.api("/requests")
    elif page in ("catalog", "inventory"):
        ctx["rows"] = await client.api(
            "/apis?"
            + urlencode(
                {
                    "inventory": str(page == "inventory").lower(),
                    "q": ctx["query"] if page == "catalog" else "",
                }
            )
        )
    elif page in ("mine", "inbox"):
        ctx["rows"] = await client.api("/requests?incoming=" + str(page == "inbox").lower())
    elif page == "audit":
        ctx["rows"] = await client.api("/audit")


async def go(page):
    window.history.pushState(None, "", "#/" + page)
    ctx["trial"] = ""
    await load()


async def refresh_session():
    ctx["me"] = await client.api("/me")
    await load()


async def login(persona=None):
    if persona:
        token = await client.api("/demo/" + persona, "POST")
        client.store.setItem("access", token["access_token"])
        await refresh_session()
    else:
        client.signin(ctx["config"])


async def logout():
    client.store.removeItem("access")
    ctx["me"] = None
    await go("catalog")
    if not ctx["config"]["demo"]:
        window.location.assign(
            ctx["config"]["domain"]
            + "/logout?"
            + urlencode(
                {
                    "client_id": ctx["config"]["client_id"],
                    "logout_uri": str(window.location.origin) + "/",
                }
            )
        )


async def search():
    ctx["query"] = value("search")
    await load()


async def register():
    chosen = [value(k) for k in ("sandbox", "production") if value(k)]
    if not chosen:
        raise ValueError("接続先を一つ以上選んでください")
    bindings = ctx["me"]["targets"]
    spec_text = value("spec")
    files = document.getElementById("spec-file").files
    if files.length:
        file = files.item(0)
        if file.size > 500000:
            raise ValueError("500KB以内のファイルを選んでください")
        spec_text = str(await file.text())
    data = {
        "base_path": value("base-path"),
        "name": value("name"),
        "summary": value("summary"),
        "owner": bindings[chosen[0]]["owner"],
        "targets": {bindings[k]["environment"]: k for k in chosen},
        "spec": json.loads(spec_text),
    }
    asset = await client.api("/apis", "POST", data)
    await go("api/" + asset["id"])
    ctx["message"] = "下書きを保存しました。仕様を確認して公開してください。"


async def publication(asset):
    await client.api(
        "/apis/" + asset["id"] + "/publication?published=" + str(not asset["published"]).lower(), "PUT"
    )
    await load()
    ctx["message"] = "掲載状態を更新しました"


async def apply(asset):
    await client.api(
        "/apis/" + asset["id"] + "/requests",
        "POST",
        {"project": value("project"), "environment": value("environment"), "reason": value("reason")},
    )
    await go("mine")
    ctx["message"] = "利用申請を送信しました"


async def decide(row, decision):
    await client.api(
        "/requests/" + row["id"],
        "POST",
        {"action": decision, "revision": row["revision"], "reason": value("reason-" + row["id"])},
    )
    await load()
    ctx["message"] = "申請状態を更新しました"


async def invoke(asset):
    env, project = value("trial-grant").split("/")
    path = value("trial-path")
    if not path.startswith("/") or "#" in path:
        raise ValueError("/ で始まる操作パスを指定してください")
    method = value("trial-method")
    options = {
        "method": method,
        "headers": {
            "Authorization": "Bearer " + str(client.store.getItem("access")),
            "Content-Type": "application/json",
        },
    }
    if method not in ("GET", "DELETE") and value("trial-body"):
        options["body"] = value("trial-body")
    url = client.prefix + "/invoke/" + asset["id"] + "/" + env + "/" + project + path
    result = await pyfetch(url, **options)
    ctx["trial"] = f"HTTP {result.status}\n" + (await result.string())[:6000]


def login_page():
    t.h1("継手APIにログイン")
    if ctx["config"]["demo"]:
        t.p("ローカルで試す役割を選んでください。", classes="muted")
        with t.div(classes="btn-grouping"):
            for key, title in [
                ("provider", "提供チーム"),
                ("consumer", "利用チーム"),
                ("auditor", "監査担当"),
            ]:
                btn(title, login, key, primary=key == "consumer")
    else:
        btn("社内アカウントでログイン", login, primary=True)


def inventory_form():
    t.h2("APIを登録")
    with t.div(classes="box"):
        field("API名", "name")
        field("用途・説明", "summary")
        for env in ("sandbox", "production"):
            opts = [("", "指定しない")] + [
                (k, k + " · " + v["owner"])
                for k, v in ctx["me"]["targets"].items()
                if v["environment"] == env
            ]
            field(LABEL[env] + "の接続先", env, options=opts)
        field("接続先のベースパス（任意）", "base-path", placeholder="/inventory/v1")
        with t.label(classes="field"):
            t.span("OpenAPIファイル（JSON）")
            t.input(id="spec-file", type="file", accept=".json,application/json", classes="form-control")
        field(
            "またはOpenAPI定義を貼り付け（JSON）",
            "spec",
            textarea=True,
            text=json.dumps(SAMPLE, ensure_ascii=False, indent=2) if ctx["config"]["demo"] else "",
        )
        btn("下書きを保存", register, primary=True)


def cards():
    if not ctx["rows"]:
        t.p("該当するAPIはありません。", classes="muted")
    for row in ctx["rows"]:
        with t.article(classes="box"):
            t.h2(row["name"])
            t.p(row["summary"])
            t.p(row["owner"] + " · " + ("公開中" if row["published"] else "未掲載"), classes="muted")
            btn("詳細を見る", go, "api/" + row["id"])


def detail_page():
    a = ctx["detail"]
    if not a:
        t.p("APIを読み込み中…")
        return
    t.h1(a["name"])
    t.p(a["summary"])
    t.p(a["owner"] + " · " + ("公開中" if a["published"] else "未掲載"), classes="muted")
    if a["owner"] in ctx["me"]["owners"]:
        btn("掲載を取り下げる" if a["published"] else "公開する", publication, a, primary=True)
    with t.div(classes="box"):
        t.h2("操作と仕様")
        for path, ops in a["spec"]["paths"].items():
            for method, op in ops.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    t.p(f"{method.upper()}  {path}　{op.get('summary', '')}", classes="code")
        with t.details():
            t.summary("OpenAPI定義を表示")
            t.pre(json.dumps(a["spec"], ensure_ascii=False, indent=2), classes="code")
    if a["published"] and ctx["me"]["projects"]:
        with t.div(classes="box"):
            t.h2("利用申請")
            field("利用プロジェクト", "project", options=[(p, p) for p in ctx["me"]["projects"]])
            field("環境", "environment", options=[(e, LABEL[e]) for e in a["environments"]])
            field("利用目的", "reason", textarea=True)
            btn("申請する", apply, a, primary=True)
    rights = [r for r in ctx.get("rights", []) if r["asset_id"] == a["id"] and r["status"] == "approved"]
    if rights:
        with t.div(classes="box"):
            t.h2("APIを呼び出す")
            field(
                "承認済みの環境とプロジェクト",
                "trial-grant",
                options=[
                    (
                        r["environment"] + "/" + r["project"],
                        LABEL[r["environment"]] + " · " + r["project"],
                    )
                    for r in rights
                ],
            )
            example = rights[0]
            root = f"{window.location.origin}{client.prefix}/invoke/{a['id']}/{example['environment']}/{example['project']}"
            t.p("呼び出し先　" + root, classes="code")
            field(
                "メソッド",
                "trial-method",
                options=[(m, m) for m in ("GET", "POST", "PUT", "PATCH", "DELETE")],
            )
            field("操作パス", "trial-path", text=next(iter(a["spec"]["paths"])))
            field("リクエスト本文", "trial-body", textarea=True)
            btn("実行する", invoke, a)
            if ctx["trial"]:
                t.pre(ctx["trial"], classes="code")


def rights_page(incoming):
    if not ctx["rows"]:
        t.p("申請はありません。", classes="muted")
    for row in ctx["rows"]:
        with t.article(classes="box"):
            t.h2(row.get("asset_name") or row["asset_id"])
            t.p(
                f"{row['project']} · {LABEL[row['environment']]} · {LABEL[row['status']]}",
                classes="state",
            )
            t.p(row["reason"])
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


@app.page()
class Portal(Page):
    def populate(self):
        user = ctx["me"]
        with t.header():
            t.span("継手API", classes="brand")
            if user:
                btn("ログアウト", logout)
        with t.div(classes="wrap"):
            if ctx["message"]:
                t.div(ctx["message"], role="alert", classes="notice error" if ctx["error"] else "notice")
            if not ctx["config"]:
                t.p("カタログを読み込み中…")
                return
            if not user:
                login_page()
                return
            with t.nav():
                for page, title in PAGES.items():
                    if page not in ("inventory", "inbox") or user["owners"]:
                        btn(title, go, page, primary=route() == page)
            page = route()
            if page.startswith("api/"):
                detail_page()
                return
            t.h1(PAGES.get(page, "APIカタログ"), classes="section-top")
            if page == "catalog":
                field(
                    "キーワードで検索",
                    "search",
                    text=ctx["query"],
                    placeholder="API名、用途、提供チーム、OpenAPIの仕様",
                )
                btn("検索", search)
                cards()
            elif page == "inventory":
                inventory_form()
                t.h2("登録したAPI")
                cards()
            elif page in ("mine", "inbox"):
                rights_page(page == "inbox")
            elif page == "audit":
                if not ctx["rows"]:
                    t.p("記録はありません。")
                for row in ctx["rows"]:
                    with t.article(classes="box"):
                        t.strong(row["action"] + " · " + row["actor"])
                        t.p(f"{row['at']}　{row['project']}　{row['environment']}　{row['detail']}")
                        t.small("API " + row["asset_id"] + " / リクエスト " + row["request_id"])


async def start():
    client.prefix = (await (await pyfetch("/entry.json")).json())["api_prefix"]
    ctx["config"] = await client.api("/config")
    await client.callback(ctx["config"])
    if client.store.getItem("access"):
        await refresh_session()


add_event_listener(window, "popstate", action(load))
render()
asyncio.ensure_future(run(start))
