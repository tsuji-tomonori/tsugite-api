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
    "trace": "",
    "page": 1,
    "env": "",
    "audit_id": "",
    "audit_action": "",
    "audit_offset": 0,
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
ACTIONS = {
    "register": "下書き登録",
    "publish": "公開",
    "unpublish": "掲載取り下げ",
    "apply": "利用申請",
    "approve": "承認",
    "reject": "却下",
    "withdraw": "申請取り下げ",
    "revoke": "権限取消",
    "invoke.start": "呼び出し開始",
    "invoke.end": "応答",
    "invoke.denied": "呼び出し拒否",
    "invoke.error": "呼び出しエラー",
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
                    t.option(title, value=key, selected=(key == text))
        elif textarea:
            t.textarea(text, id=name, classes="form-control", placeholder=placeholder)
        else:
            t.input(id=name, value=text, classes="form-control", placeholder=placeholder)


async def load():
    if not ctx["me"]:
        return
    page = route()
    if page.startswith("api/"):
        if (ctx["detail"] or {}).get("id") != page[4:]:
            ctx.update(trial="", trace="")
        ctx["detail"] = await client.api("/apis/" + quote(page[4:], safe=""))
        ctx["rights"] = await client.api("/requests?" + urlencode({"asset_id": ctx["detail"]["id"]}))
    elif page in ("catalog", "inventory"):
        params = {"inventory": str(page == "inventory").lower(), "page": ctx["page"], "q": ctx["query"]}
        if ctx["env"]:
            params["environment"] = ctx["env"]
        result = await client.api("/catalog-page?" + urlencode(params))
        ctx.update(
            rows=result["items"], total=result["total"], page=result["page"], size=result["page_size"]
        )
    elif page in ("mine", "inbox"):
        ctx["rows"] = await client.api("/requests?incoming=" + str(page == "inbox").lower())
    elif page == "audit":
        ctx["rows"] = await client.api(
            "/audit?"
            + urlencode(
                {
                    "request_id": ctx["audit_id"],
                    "action": ctx["audit_action"],
                    "offset": ctx["audit_offset"],
                    "limit": 31,
                }
            )
        )


async def go(page):
    if page in ("catalog", "inventory") and page != route():
        ctx.update(page=1, query="", env="")
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
    ctx.update(query=value("search"), env=value("filter-env"), page=1)
    await load()


async def turn_page(n):
    ctx["page"] = n
    await load()


async def audit_filter():
    ctx.update(audit_id=value("audit-id"), audit_action=value("audit-action"), audit_offset=0)
    await load()


async def trace_lookup(trace):
    ctx.update(audit_id=trace, audit_action="", audit_offset=0)
    await go("audit")


async def audit_page(offset):
    ctx["audit_offset"] = offset
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
    ctx["trace"] = str(result.headers.get("x-request-id") or "")
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
    t.p("接続先とOpenAPI仕様を登録し、下書きの詳細画面で公開します。", classes="muted")
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
    count, page, size = ctx["total"], ctx["page"], ctx["size"]
    start = (page - 1) * size + 1 if count else 0
    pages = max(1, (count + size - 1) // size)
    with t.form(classes="searchbar", on_submit=action(search)):
        field("キーワードで検索", "search", text=ctx["query"], placeholder="API名、用途、提供元、操作名")
        field(
            "提供環境",
            "filter-env",
            options=[("", "すべての環境"), ("sandbox", "検証"), ("production", "本番")],
            text=ctx["env"],
        )
        t.button("検索", type="submit", classes="btn btn-primary")
    with t.div(classes="results-head"):
        t.h2(f"API一覧（{count}件）")
        t.span(f"{start}–{min(count, page * size)} 件を表示", classes="muted")
    if not count:
        with t.div(classes="empty"):
            t.h3("該当するAPIはありません。")
            t.p("キーワードや提供環境を変更して検索してください。")
    with t.div(classes="card-grid"):
        for row in ctx["rows"]:
            with t.article(classes="asset-card"):
                with t.div(classes="asset-meta"):
                    t.span("API", classes="asset-symbol")
                    t.span(row["owner"], classes="owner")
                with t.h3():
                    t.a(row["name"], href="#/api/" + row["id"], classes="asset-title")
                t.p(row["summary"], classes="description")
                with t.div(classes="card-foot"):
                    with t.div(classes="pills"):
                        for env in row["environments"]:
                            t.span(LABEL[env], classes="pill " + env)
                        if not row["published"]:
                            t.span("下書き", classes="pill pending")
                    if route() == "inventory" and row["published"]:
                        t.span("公開中", classes="pill approved")
    if pages > 1:
        with t.div(classes="pager"):
            if page > 1:
                btn("前へ", turn_page, page - 1)
            t.span(f"{page} / {pages} ページ")
            if page < pages:
                btn("次へ", turn_page, page + 1)


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
    for row in ctx.get("rights", []):
        with t.div(classes="grant-status"):
            t.strong(
                row["project"] + " · " + LABEL[row["environment"]] + " · " + LABEL[row["status"]],
                classes="pill " + row["status"],
            )
            if row.get("decision_reason"):
                t.span("判断理由　" + row["decision_reason"])
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
                text=next(
                    (
                        m.upper()
                        for m in next(iter(a["spec"]["paths"].values()))
                        if m in ("get", "post", "put", "patch", "delete")
                    ),
                    "GET",
                ),
            )
            field("操作パス", "trial-path", text=next(iter(a["spec"]["paths"])))
            field("リクエスト本文", "trial-body", textarea=True)
            btn("実行する", invoke, a)
            if ctx["trial"]:
                t.pre(ctx["trial"], classes="code")
                if ctx["trace"]:
                    t.small("リクエストID　" + ctx["trace"], classes="mono")
                    btn("この実行の監査履歴", trace_lookup, ctx["trace"])


def rights_page(incoming):
    if not ctx["rows"]:
        t.p("申請はありません。", classes="muted")
    for row in ctx["rows"]:
        with t.article(classes="box"):
            t.h2(row.get("asset_name") or row["asset_id"])
            t.p(
                f"{row['project']} · {LABEL[row['environment']]} · {LABEL[row['status']]}",
                classes="pill " + row["status"],
            )
            t.p("利用目的　" + row["reason"])
            if row.get("decision_reason"):
                t.p("判断理由　" + row["decision_reason"], classes="decision")
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


def audit_view():
    with t.form(classes="searchbar", on_submit=action(audit_filter)):
        field("リクエストID", "audit-id", text=ctx["audit_id"], placeholder="実行結果に表示されたID")
        field(
            "操作",
            "audit-action",
            options=[("", "すべての操作"), *ACTIONS.items()],
            text=ctx["audit_action"],
        )
        t.button("絞り込む", type="submit", classes="btn btn-primary")
    if not ctx["rows"]:
        t.p("条件に一致する記録はありません。", classes="empty")
    for row in ctx["rows"][:30]:
        with t.article(classes="audit-row"):
            with t.div(classes="audit-top"):
                t.strong(ACTIONS.get(row["action"], row["action"]), classes="event-type")
                t.small(row["at"][:19].replace("T", " ") + " UTC", classes="muted")
            t.p(row["action"] + " · " + row["actor"], classes="mono")
            t.p(
                "提供元 "
                + row["owner"]
                + "　"
                + row["project"]
                + "　"
                + LABEL.get(row["environment"], "")
                + "　"
                + row["detail"]
            )
            t.small("API " + row["asset_id"] + " / リクエスト " + row["request_id"], classes="mono")
    with t.div(classes="pager"):
        if ctx["audit_offset"]:
            btn("新しい記録", audit_page, ctx["audit_offset"] - 30)
        if len(ctx["rows"]) > 30:
            btn("以前の記録", audit_page, ctx["audit_offset"] + 30)


@app.page()
class Portal(Page):
    def populate(self):
        user, page = ctx["me"], route()
        title = PAGES.get(page, "APIの詳細" if page.startswith("api/") else "APIを登録")
        with t.header(classes="mast"):
            with t.div(classes="identity"):
                t.span("", classes="brand-mark", aria_hidden="true")
                t.strong("継手API", classes="brand")
                t.span("APIポータル", classes="product")
            if user:
                t.span(
                    " / ".join(sorted(set(user["owners"] + user["projects"]))) or "監査担当",
                    classes="project",
                )
                btn("ログアウト", logout)
        if not ctx["config"] or not user:
            with t.section(classes="login box"):
                if ctx["message"]:
                    t.div(ctx["message"], role="alert", classes="notice error")
                if ctx["config"]:
                    login_page()
                else:
                    t.p("カタログを読み込み中…")
            return
        with t.div(classes="workspace"):
            with t.nav(classes="rail", aria_label="ポータル"):
                for label, pages in [
                    ("ワークスペース", ("catalog", "mine")),
                    ("提供者メニュー", ("inventory", "inbox")),
                    ("ガバナンス", ("audit",)),
                ]:
                    if label == "提供者メニュー" and not user["owners"]:
                        continue
                    with t.div(classes="nav-group"):
                        t.small(label)
                        for target in pages:
                            active = page == target or (page == "register" and target == "inventory")
                            t.button(
                                PAGES[target],
                                type="button",
                                classes="nav-item active" if active else "nav-item",
                                aria_current="page" if active else "false",
                                on_click=action(go, target),
                            )
            with t.section(classes="content"):
                t.div("継手API　 /　" + title, classes="crumb")
                if ctx["message"]:
                    t.div(
                        ctx["message"],
                        role="alert",
                        classes="notice error" if ctx["error"] else "notice",
                    )
                if page.startswith("api/"):
                    detail_page()
                    return
                with t.div(classes="page-heading"):
                    with t.div():
                        t.h1(title)
                        descriptions = {
                            "catalog": "公開されたAPIを探し、プロジェクトでの利用を申請できます。",
                            "inventory": "チームの下書きと公開中のAPIを管理します。",
                            "mine": "プロジェクトの申請状況と、承認されたAPIを確認できます。",
                            "inbox": "利用目的と環境を確認し、チームに届いた申請を判断します。",
                            "audit": "公開、申請、判断、呼び出しの記録を追跡できます。",
                        }
                        if page in descriptions:
                            t.p(descriptions[page], classes="subtitle")
                    if page == "inventory":
                        btn("APIを登録", go, "register", primary=True)
                if page in ("catalog", "inventory"):
                    cards()
                elif page == "register" and user["owners"]:
                    inventory_form()
                elif page in ("mine", "inbox"):
                    rights_page(page == "inbox")
                elif page == "audit":
                    audit_view()


async def start():
    client.prefix = (await (await pyfetch("/entry.json")).json())["api_prefix"]
    ctx["config"] = await client.api("/config")
    await client.callback(ctx["config"])
    if client.store.getItem("access"):
        await refresh_session()


add_event_listener(window, "popstate", action(load))
render()
asyncio.ensure_future(run(start))
