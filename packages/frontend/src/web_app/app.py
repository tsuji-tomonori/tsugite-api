import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import api_docs
import chat_views
import client
import guide_views
import login_views
import operation_views
import product_views
import workspace_views
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
    "filters": {
        "hours": "24",
        "minutes": "60",
        "measure": "calls",
        "unit": "",
        "asset": "",
        "project": "",
        "env": "",
        "status": "",
        "start": "",
        "end": "",
    },
    "badge": 0,
    "trial": "",
    "trace": "",
    "page": 1,
    "env": "",
    "audit_id": "",
    "audit_action": "",
    "audit_offset": 0,
}
INITIAL_STATE = deepcopy(ctx)

LABEL = {
    "pending": "承認待ち",
    "approved": "利用中",
    "rejected": "却下",
    "revoked": "取消済み",
    "withdrawn": "取下げ済み",
    "sandbox": "検証",
    "staging": "準本番",
    "production": "本番",
}
ACTIONS = {
    "register": "下書き登録",
    "publish": "公開",
    "unpublish": "掲載取り下げ",
    "apply": "利用申請",
    "approve": "承認",
    "step.approve": "中間段階を承認",
    "reject": "却下",
    "withdraw": "申請取り下げ",
    "revoke": "権限取消",
    "edit": "掲載内容変更",
    "delete": "API削除",
    "member.add": "ユーザー追加",
    "member.delete": "ユーザー削除",
    "notify": "通知送信",
    "alert.configure": "ルール変更",
    "alert.trigger": "しきい値到達",
    "invoke.start": "呼び出し開始",
    "invoke.end": "応答",
    "invoke.denied": "呼び出し拒否",
    "invoke.error": "呼び出しエラー",
}
SAMPLE = {
    "openapi": "3.0.3",
    "info": {"title": "在庫照会", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {"summary": "在庫一覧を取得", "responses": {"200": {"description": "在庫一覧"}}}
        },
        "/items/{sku}": {
            "get": {
                "summary": "商品コードで在庫を取得",
                "parameters": [
                    {
                        "in": "path",
                        "name": "sku",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "TS-01",
                    }
                ],
                "responses": {
                    "200": {"description": "該当商品の在庫"},
                    "404": {"description": "商品が見つかりません"},
                },
            }
        },
    },
}
PAGES = {
    "home": "ホーム",
    "dashboard": "利用状況",
    "inquiries": "問い合わせ",
    "guide": "使い方ガイド",
    "keys": "APIキー",
    "workspace": "組織・プロジェクト",
    "metrics": "メトリクス",
    "logs": "アクセスログ",
    "members": "ユーザー管理",
    "notifications": "通知",
    "alerts": "アラート",
    "catalog": "APIカタログ",
    "mine": "自分の申請",
    "inventory": "提供するAPI",
    "inbox": "届いた申請",
    "audit": "監査履歴",
}


def value(name):
    return str(document.getElementById(name).value).strip()


def route():
    return str(window.location.hash).lstrip("#/") or "home"


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
        t.span(label, id=name + "-label")
        if options is not None:
            with t.select(id=name, aria_labelledby=name + "-label", classes="form-select"):
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
    if page == "dashboard":
        for key in ("dashboard", "home_metrics", "recent_logs"):
            ctx.pop(key, None)
    elif page == "metrics":
        ctx.pop("metrics", None)
    if page != "keys":
        ctx.pop("issued_key", None)
    ctx["me"], badge = await asyncio.gather(client.api("/me"), client.api("/notifications/count"))
    ctx["badge"] = badge["unread"]
    if page in ("workspace", "keys"):
        ctx["workspace"] = await client.api("/workspace")
        if page == "keys":
            ctx["keys"], ctx["key_assets"] = await asyncio.gather(
                client.api("/keys"), client.api("/key-assets")
            )
    elif page == "register":
        ctx["policy_directory"] = await client.api("/workspace")
    elif page == "dashboard":
        results = await asyncio.gather(
            client.api("/dashboard"),
            client.api("/metrics?minutes=60"),
            client.api("/access-logs"),
            return_exceptions=True,
        )
        for key, result in zip(("dashboard", "home_metrics", "recent_logs"), results, strict=True):
            if not isinstance(result, BaseException):
                ctx[key] = result
        for result in results:
            if isinstance(result, BaseException):
                raise result
    elif page == "inquiries":
        params = {
            "incoming": str(ctx.get("inquiry_incoming", False)).lower(),
            "offset": ctx.get("inquiry_offset", 0),
        }
        ctx["inquiries"] = await client.api("/inquiries?" + urlencode(params))
    elif page == "members" and ctx["me"]["admin"]:
        ctx["members"] = await client.api(
            "/members?" + urlencode({"cursor": ctx.get("member_cursor", "")})
        )
    elif page in ("notifications", "alerts"):
        ctx["targets"] = (
            await client.api("/management-targets") if ctx["me"]["owners"] or ctx["me"]["admin"] else []
        )
        if page == "notifications":
            ctx["notices"] = await client.api(
                "/notifications?offset=" + str(ctx.get("notice_offset", 0))
            )
        else:
            ctx["rules"] = await client.api("/alerts")
    elif page in ("metrics", "logs"):
        ctx["workspace"] = await client.api("/workspace")
        if ctx["filters"]["unit"] not in ctx["workspace"]["leads"]:
            ctx["filters"]["unit"] = ""
        ctx["dims"] = await client.api(
            "/metric-dimensions?" + urlencode({"unit": ctx["filters"]["unit"]})
        )
        params = time_params()
        if page == "metrics":
            ctx["metrics"] = await client.api(
                "/metrics?" + urlencode({**params, "minutes": ctx["filters"]["minutes"]})
            )
        else:
            ctx["log_rows"] = await client.api(
                "/access-logs?"
                + urlencode(
                    {
                        **params,
                        "request_id": ctx.get("access_id", ""),
                        "offset": ctx.get("log_offset", 0),
                    }
                )
            )
    elif page.startswith(("api/", "edit/")):
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


async def go(page, *, query=None):
    if page != "workspace":
        for name in ("workspace_usage", "membership_draft", "unit_draft", "directory_candidates"):
            ctx.pop(name, None)
    if query is not None or (page in ("catalog", "inventory") and page != route()):
        ctx.update(page=1, query=query or "", env="")
    if window.matchMedia("(max-width: 780px)").matches:
        ctx["nav_open"] = False
    window.history.pushState(None, "", "#/" + page)
    ctx["trial"] = ""
    await load()


async def refresh_session():
    ctx["me"] = await client.api("/me")
    await load()


async def login(persona):
    token = await client.api("/demo/" + persona, "POST")
    client.store.setItem("access", token["access_token"])
    await refresh_session()


async def logout():
    portal_login = client.store.getItem("portal_login")
    client.store.removeItem("portal_login")
    client.store.removeItem("access")
    config = ctx["config"]
    ctx.clear()
    ctx.update(deepcopy(INITIAL_STATE), config=config)
    await go("home")
    if not config["demo"] and not portal_login:
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


async def inquiry_page(incoming, offset):
    ctx.update(inquiry_incoming=incoming, inquiry_offset=offset)
    await load()


async def reply_inquiry(key):
    answer = value("reply-" + key)
    if len(answer) < 2:
        raise ValueError("回答を入力してください")
    await client.api("/inquiries/" + key + "/reply", "PUT", {"answer": answer})
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


async def register(publish_now=False):
    chosen = [value(k) for k in product_views.ENV if value(k)]
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
    try:
        spec = json.loads(spec_text)
        info = spec["info"]
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("OpenAPI 3.0 / 3.1 のJSONファイルを指定してください") from exc
    data = {
        "release_note": value("release-note"),
        "offers": {
            bindings[k]["environment"]: product_views.read_offer(bindings[k]["environment"], value)
            for k in chosen
        },
        "base_path": value("base-path"),
        "name": value("name") or info.get("title", ""),
        "summary": value("summary") or info.get("description") or info.get("title", ""),
        "owner": bindings[chosen[0]]["owner"],
        "targets": {bindings[k]["environment"]: k for k in chosen},
        "spec": spec,
    }
    if route().startswith("edit/"):
        row = ctx["detail"]
        asset = await client.api("/apis/" + row["id"] + "?revision=" + str(row["revision"]), "PUT", data)
    else:
        asset = await client.api("/apis", "POST", data)
    await go("api/" + asset["id"])
    if publish_now and not asset["published"]:
        await publication(asset)
    else:
        ctx["message"] = (
            "掲載内容を保存しました"
            if asset["published"]
            else "下書きを保存しました。仕様を確認して公開してください。"
        )


async def publication(asset):
    await client.api(
        "/apis/" + asset["id"] + "/publication?published=" + str(not asset["published"]).lower(), "PUT"
    )
    await load()
    ctx["message"] = "掲載状態を更新しました"


async def change_suspension(asset):
    suspended = not asset["suspended"]
    action = "一時停止" if suspended else "再開"
    if window.confirm(asset["name"] + "への全環境のアクセスを" + action + "しますか？"):
        await client.api(
            "/apis/" + asset["id"] + "/suspension?suspended=" + str(suspended).lower(), "PUT"
        )
        await load()
        ctx["message"] = "APIへのアクセスを" + action + "しました"


async def apply(asset):
    await client.api(
        "/apis/" + asset["id"] + "/requests",
        "POST",
        {
            "project": value("project"),
            "personal": value("grant-kind") == "personal"
            or value("project") == ctx["me"]["personal_project"],
            "environment": value("environment"),
            "reason": value("reason"),
            **product_views.answers(asset, value("environment"), value),
        },
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


def theme_changed(event):
    mode = str(event.target.value)
    window.localStorage.setItem("visual-mode", mode)
    document.documentElement.setAttribute("data-mode", mode)


def set_navigation(opened):
    ctx["nav_open"] = opened
    workspace = document.getElementById("workspace")
    if workspace:
        workspace.setAttribute("data-nav", "open" if opened else "closed")
        document.getElementById("nav-toggle").setAttribute(
            "aria-expanded", "true" if opened else "false"
        )


def toggle_navigation(event):
    set_navigation(str(event.currentTarget.getAttribute("aria-expanded")) != "true")


def adapt_navigation(event):
    set_navigation(not event.matches)


async def global_search():
    await go("catalog", query=value("global-query"))


def login_page():
    if ctx["config"]["demo"]:
        t.h1("継手APIにログイン")
        t.p("ローカルで試す役割を選んでください。", classes="muted")
        with t.div(classes="btn-grouping"):
            for key, title in [
                ("provider", "提供チーム"),
                ("consumer", "利用チーム"),
                ("auditor", "監査担当"),
                ("admin", "管理者"),
            ]:
                btn(title, login, key, primary=key == "consumer")
        with t.details():
            t.summary("追加したユーザーでログイン")
            field("登録メールアドレス", "login-email")
            btn("このユーザーでログイン", login_member)
    else:
        login_views.portal_form(ctx, action, client.store, refresh_session)


async def login_member():
    await login(quote(value("login-email").lower(), safe=""))


def inventory_form(asset=None):
    item = asset or {}
    t.p(
        "出品する環境の接続先とOpenAPI 3.0 / 3.1のJSONを選びます。API名と説明はファイルから取り込めます。",
        classes="muted",
    )
    with t.div(classes="box"):
        field("API名", "name", text=item.get("name", ""))
        field("用途・説明", "summary", text=item.get("summary", ""))
        for env in product_views.ENV:
            opts = [("", "指定しない")] + [
                (k, k + " · " + v["owner"])
                for k, v in ctx["me"]["targets"].items()
                if v["environment"] == env
            ]
            field(LABEL[env] + "の接続先", env, options=opts, text=item.get("bindings", {}).get(env, ""))
            product_views.offer_editor(
                env,
                item.get("offers", {}).get(env, {}),
                field,
                bool(asset),
                ctx["policy_directory"]["units"],
            )
        field(
            "この版の変更内容",
            "release-note",
            textarea=True,
            text=item.get("release_note", ""),
            placeholder="例：在庫照会に倉庫別の検索を追加",
        )
        field(
            "接続先のベースパス（任意）",
            "base-path",
            text=item.get("base_path", ""),
            placeholder="/inventory/v1",
        )
        with t.label(classes="field"):
            t.span("OpenAPIファイル（JSON）")
            t.input(id="spec-file", type="file", accept=".json,application/json", classes="form-control")
        field(
            "またはOpenAPI定義を貼り付け（JSON）",
            "spec",
            textarea=True,
            text=json.dumps(item.get("spec", SAMPLE), ensure_ascii=False, indent=2)
            if asset or ctx["config"]["demo"]
            else "",
        )
        if asset:
            t.p(
                "仕様や接続先を変えると全環境の利用権と申請を終了します。利用条件のみの変更では、変更した環境で再申請が必要です。"
            )
        btn("変更を保存" if asset else "下書きを保存", register)
        btn("保存して公開", register, True, primary=True)


def cards():
    count, page, size = ctx["total"], ctx["page"], ctx["size"]
    start = (page - 1) * size + 1 if count else 0
    pages = max(1, (count + size - 1) // size)
    with t.div(classes="collection-tools"):
        with t.div(classes="results-head"):
            t.h2(f"API一覧（{count}件）")
            t.span(f"{start}–{min(count, page * size)} 件を表示", classes="muted")
        with t.form(classes="searchbar", on_submit=action(search)):
            field(
                "キーワードで検索",
                "search",
                text=ctx["query"],
                placeholder="API名、用途、提供元、操作名",
            )
            field(
                "提供環境",
                "filter-env",
                options=[
                    ("", "すべての環境"),
                    ("sandbox", "検証"),
                    ("staging", "準本番"),
                    ("production", "本番"),
                ],
                text=ctx["env"],
            )
            t.button("検索", type="submit", classes="btn btn-primary")
    if not count:
        with t.div(classes="empty"):
            t.h3("該当するAPIはありません。")
            t.p("キーワードや提供環境を変更して検索してください。")
    with t.div(classes="card-grid"):
        for row in ctx["rows"]:
            with t.article(classes="asset-card"):
                with t.h3():
                    t.a(row["name"], href="#/api/" + row["id"], classes="asset-title")
                t.p(row["summary"], classes="description")
                with t.div(classes="card-foot"):
                    with t.div():
                        t.strong("提供元", classes="key")
                        t.span(row["owner"], classes="owner")
                    with t.div():
                        t.strong("提供環境", classes="key")
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


async def save_policy(asset):
    data = {"visibility": value("policy-visibility")}
    for key in ("projects", "departments", "auto_departments", "delegates"):
        fields = document.querySelectorAll('input[name="policy-' + key + '"]:checked')
        data[key] = [str(fields.item(i).value) for i in range(fields.length)]
    data["auto_titles"] = [
        v.strip() for v in value("policy-titles").replace("、", ",").split(",") if v.strip()
    ]
    await client.api("/apis/" + asset["id"] + "/policy?revision=" + str(asset["revision"]), "PUT", data)
    await load()
    ctx["message"] = "公開範囲と承認ルールを保存しました"


def policy_form(asset):
    rules = ctx["policy"]
    tree = ctx["policy_directory"]["units"]
    with t.details(classes="box"):
        t.summary("公開範囲と承認ルール")
        field(
            "カタログの公開範囲",
            "policy-visibility",
            options=[("all", "全員"), ("restricted", "選択した所属だけ")],
            text=rules["visibility"],
        )
        for key, label, kind in (
            ("projects", "公開先プロジェクト", "project"),
            ("departments", "公開先部署", "department"),
            ("auto_departments", "自動承認する申請者の部署", "department"),
            ("delegates", "判断を委任する部署のリーダー", "department"),
        ):
            with t.fieldset():
                t.legend(label)
                for u in tree:
                    if u["kind"] == kind:
                        with t.label(classes="scope-choice"):
                            t.input(
                                type="checkbox",
                                name="policy-" + key,
                                value=u["id"],
                                checked=u["id"] in rules[key],
                            )
                            t.span(u["name"])
        field(
            "自動承認する役職（複数はカンマ区切り）",
            "policy-titles",
            text=", ".join(rules["auto_titles"]),
        )
        t.p(
            "部署は子孫部署を含みます。申請者の部署または役職が一致すれば自動承認し、それ以外は提供者か委任先のリーダーが判断します。"
        )
        btn("公開・承認条件を保存", save_policy, asset, primary=True)


def detail_page():
    a = ctx["detail"]
    if not a:
        t.p("APIを読み込み中…")
        return
    t.h1(a["name"])
    t.p(a["summary"])
    if ctx["me"]["admin"]:
        btn(
            "APIへのアクセスを再開" if a["suspended"] else "APIへのアクセスを一時停止",
            change_suspension,
            a,
        )
    t.p(a["owner"] + " · " + ("公開中" if a["published"] else "未掲載"), classes="muted")
    if a["owner"] in ctx["me"]["owners"]:
        btn(
            "掲載を取り下げる" if a["published"] else "公開する",
            publication,
            a,
            primary=not a["published"],
        )
        btn("内容を編集", go, "edit/" + a["id"])
        btn("APIを削除", delete_listing, a)
        policy_form(a)
        operation_views.provider_view(a, ctx, field, btn, load)
    with t.details(classes="box"):
        t.summary("OpenAPI定義を表示")
        t.pre(json.dumps(a["spec"], ensure_ascii=False, indent=2), classes="code")
    for row in ctx.get("rights", []):
        with t.div(classes="grant-status"):
            if row.get("subject"):
                t.small("個人の利用権")
            t.strong(
                row["project"] + " · " + LABEL[row["environment"]] + " · " + LABEL[row["status"]],
                classes="pill " + row["status"],
            )
            if row.get("decision_reason"):
                t.span("判断理由　" + row["decision_reason"])
    product_views.release_history(a)
    api_docs.view(a, ctx.get("rights", []), ctx.get("keys", []), subject=ctx["me"]["subject"])
    if a["published"]:
        with t.div(classes="box"):
            t.h2("利用申請")
            field(
                "利用プロジェクト",
                "project",
                options=[(p, p) for p in ctx["me"]["projects"]]
                + [(ctx["me"]["personal_project"], "個人ワークスペース")],
            )
            field(
                "申請対象",
                "grant-kind",
                options=[("project", "プロジェクト全員"), ("personal", "自分だけ")],
            )
            product_views.application_form(a, field)
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
            btn("実行する", invoke, a, primary=True)
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
            if row.get("applicant"):
                t.p(
                    ("個人申請" if row.get("subject") else "プロジェクト申請")
                    + "　申請者 "
                    + row["applicant"]
                )
            t.p("利用目的　" + row["reason"])
            stage = {"department": "所属部署の承認待ち", "provider": "提供者の承認待ち"}.get(
                row.get("stage")
            )
            if row.get("stage", "") and row["stage"].startswith("unit/"):
                stage = row["stage"][5:] + " 部署の承認待ち"
            if stage:
                t.p(stage)
            evidence = row.get("application", {})
            for decision in evidence.get("decisions", []):
                t.p(
                    product_views.step_label(decision["stage"])
                    + " · "
                    + ACTIONS[decision["action"]]
                    + " · "
                    + decision["actor"]
                    + "　"
                    + decision["reason"]
                )
            if evidence.get("terms_accepted"):
                with t.details():
                    t.summary("同意済みの利用規約")
                    t.p(evidence["terms"], classes="terms-text")
            for label, answer in evidence.get("answers", {}).items():
                t.p(label + "　" + answer)
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
    btn("業務監査をダウンロード", download_audit)
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


def role_title():
    me = ctx["me"]
    return (
        "管理者"
        if me["admin"]
        else "提供者"
        if me["owners"]
        else "監査担当"
        if me["auditor"]
        else "利用者"
    )


def dashboard_view():
    summary = ctx.get("dashboard")
    t.p(role_title() + "としての利用状況", classes="subtitle")
    if summary is None:
        t.p("利用状況の件数を取得できませんでした。")
    else:
        with t.div(classes="stat-grid"):
            cards = [
                ("直近24時間の呼び出し", summary["calls"]),
                ("直近24時間のエラー", summary["errors"]),
            ]
            if ctx["me"]["owners"] or ctx["me"]["admin"]:
                cards.append(("管理対象のAPI", summary["inventory"]))
            cards.extend([("承認待ち", summary["pending"]), ("利用中の契約", summary["approved"])])
            for label, count in cards:
                with t.article(classes="stat"):
                    t.span(label)
                    t.strong(str(count))
    with t.div(classes="home-panels"):
        with t.section(classes="box"):
            t.h2("呼び出し件数の推移")
            t.p("直近24時間・1時間ごと（UTC）", classes="muted")
            data = ctx.get("home_metrics")
            if data is None:
                t.p("メトリクスを取得できませんでした。")
            else:
                graph(data["points"], "calls", data["minutes"])
            btn("メトリクスを開く", go, "metrics")
        with t.section(classes="box"):
            t.h2("最近の呼び出し")
            logs = ctx.get("recent_logs")
            for row in (logs or [])[:4]:
                with t.div(classes="recent-call"):
                    t.strong(str(row["status"]))
                    t.span(row["method"] + " " + (row["operation"] or "操作未確定"))
                    t.small(row["at"][11:19] + " UTC")
            if logs is None:
                t.p("最近の呼び出しを取得できませんでした。")
            elif not logs:
                t.p("直近24時間の呼び出しはありません。", classes="muted")
            btn("アクセスログを開く", go, "logs")
    if summary is None or data is None or logs is None:
        btn("利用状況を再読み込み", load)
    with t.div(classes="box"):
        t.h2("業務メニュー")
        with t.div(classes="btn-grouping"):
            btn("APIを探す", go, "catalog", primary=True)
            if ctx["me"]["owners"]:
                btn("新しいAPIを登録", go, "register")
                btn("届いた申請を確認", go, "inbox")
            if ctx["me"]["admin"]:
                btn("ユーザーを管理", go, "members")
            if ctx["me"]["admin"] or ctx["me"]["owners"]:
                btn("利用者へのお知らせ", go, "notifications")
            btn("メトリクスを分析", go, "metrics")


async def member_add():
    await client.api(
        "/members",
        "POST",
        {
            "email": value("member-email"),
            "role": value("member-role"),
            "project": value("member-project"),
        },
    )
    await load()
    ctx["message"] = "ユーザーを追加しました"


async def member_remove(row):
    if not window.confirm(row["username"] + " を削除してログインを停止しますか？"):
        return
    await client.api(
        "/members/" + quote(row["subject"], safe="") + "?" + urlencode({"username": row["username"]}),
        "DELETE",
    )
    ctx["member_cursor"] = ""
    await load()


async def member_page(cursor):
    ctx["member_cursor"] = cursor
    await load()


def members_view():
    data = ctx["members"]
    with t.div(classes="box"):
        t.h2("ユーザーを追加")
        field("メールアドレス", "member-email")
        field("役割", "member-role", options=[("consumer", "利用者"), ("provider", "提供者")])
        field("所属プロジェクト", "member-project", options=[(p, p) for p in data["projects"]])
        btn("追加する", member_add, primary=True)
    t.h2("登録ユーザー")
    for row in data["items"]:
        with t.div(classes="compact-row"):
            t.strong(row["username"])
            t.span(ROLE_LABELS.get(row["role"], row["role"]) + "　" + row.get("project", ""))
            if row["subject"] != ctx["me"]["subject"]:
                btn("削除", member_remove, row)
    if data["next"]:
        btn("次のユーザー", member_page, data["next"])
    if ctx.get("member_cursor"):
        btn("先頭に戻る", member_page, "")


def target_options():
    return [
        (r["id"], f"{r['name']} · {r['project']} · {LABEL[r['environment']]}")
        for r in ctx.get("targets", [])
    ]


async def send_notice():
    if ctx["me"]["admin"]:
        project, asset = value("notify-project"), ""
    else:
        asset, project, _ = value("notify-target").split("/")
    await client.api(
        "/notifications",
        "POST",
        {
            "title": value("notify-title"),
            "body": value("notify-body"),
            "asset_id": asset,
            "project": project,
        },
    )
    await load()
    ctx["message"] = "通知を送信しました"


async def read_notice(key):
    await client.api("/notifications/" + key + "/read", "PUT")
    await load()


async def more_notices(offset):
    ctx["notice_offset"] = offset
    await load()


def notices_view():
    me = ctx["me"]
    rows = ctx["notices"]["items"]
    if me["admin"] or me["owners"] and ctx.get("targets"):
        with t.details(classes="box"):
            t.summary("利用者に通知を送る")
            if me["admin"]:
                field(
                    "送信先",
                    "notify-project",
                    options=[("*", "全プロジェクト")] + [(p, p) for p in me["known_projects"]],
                )
            else:
                field("送信先のAPIと利用プロジェクト", "notify-target", options=target_options())
            field("件名", "notify-title")
            field("お知らせ本文", "notify-body", textarea=True)
            btn("通知を送信", send_notice, primary=True)
    if not rows:
        t.p("届いている通知はありません。", classes="empty")
    for n in rows:
        with t.article(classes="box"):
            t.small(
                ("未読" if n["unread"] else "既読") + " · " + n["at"][:16].replace("T", " ") + " UTC",
                classes="muted",
            )
            t.h2(n["title"])
            t.p(n["body"])
            t.small("送信者 " + n["sender"] + "　宛先 " + n["project"])
            if n["unread"]:
                btn("既読にする", read_notice, n["id"])
    if ctx.get("notice_offset", 0):
        btn("新しい通知", more_notices, ctx["notice_offset"] - 30)
    if len(rows) == 30:
        btn("以前の通知", more_notices, ctx.get("notice_offset", 0) + 30)


MEASURES = {
    "calls": "呼び出し件数",
    "success": "成功件数",
    "errors": "エラー件数",
    "denied": "拒否件数",
    "avg_ms": "平均応答時間（ms）",
    "max_ms": "最大応答時間（ms）",
}
ROLE_LABELS = {"provider": "提供者", "consumer": "利用者", "admin": "管理者", "auditor": "監査担当"}


def time_params():
    f = ctx["filters"]
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=int(f["hours"]))
    return {
        k: v
        for k, v in {
            "start": f["start"] or start.isoformat(),
            "end": f["end"] or end.isoformat(),
            "unit": f["unit"],
            "asset_id": f["asset"],
            "project": f["project"],
            "environment": f["env"],
            "status": f["status"],
        }.items()
        if v
    }


async def apply_filters():
    f = {k: value("f-" + k) for k in ctx["filters"]}
    ctx["filters"] = f
    ctx["log_offset"] = 0
    await load()


def filters_view(chart):
    f = ctx["filters"]
    dims = ctx["dims"]

    def choice(k, title, opts):
        field(title, "f-" + k, options=opts, text=f[k])

    with t.div(classes="box"):
        with t.div(classes="filter-grid"):
            choices = [
                (u["id"], u["name"])
                for u in ctx["workspace"]["units"]
                if u["id"] in ctx["workspace"]["leads"]
            ]
            if choices:
                choice("unit", "集計する部署・プロジェクト", [("", "通常の閲覧範囲")] + choices)
            else:
                t.input(type="hidden", id="f-unit", value="")
            choice(
                "hours",
                "期間",
                [("1", "過去1時間"), ("24", "過去24時間"), ("168", "過去7日"), ("720", "過去30日")],
            )
            choice(
                "asset", "対象API", [("", "すべて")] + sorted({(v["asset_id"], v["name"]) for v in dims})
            )
            choice(
                "project",
                "利用プロジェクト",
                [("", "すべて")] + sorted({(v["project"], v["project"]) for v in dims if v["project"]}),
            )
            choice(
                "env",
                "対象環境",
                [("", "すべて"), ("sandbox", "検証"), ("staging", "準本番"), ("production", "本番")],
            )
            field("HTTPステータス", "f-status", text=f["status"], placeholder="すべて")
            if chart:
                choice("minutes", "集計間隔", [(str(n), str(n) + "分") for n in (1, 5, 15, 60, 1440)])
                choice("measure", "表示指標", list(MEASURES.items()))
            else:
                t.input(type="hidden", id="f-minutes", value=f["minutes"])
                t.input(type="hidden", id="f-measure", value=f["measure"])
        with t.details():
            t.summary("日時を指定（UTC）")
            field("開始日時", "f-start", text=f["start"], placeholder="2026-11-21T00:00:00Z")
            field("終了日時", "f-end", text=f["end"], placeholder="2026-11-21T01:00:00Z")
        btn("条件を適用", apply_filters, primary=True)


async def inspect_bucket(at, minutes):
    begin = datetime.fromisoformat(at)
    ctx["filters"].update(start=begin.isoformat(), end=(begin + timedelta(minutes=minutes)).isoformat())
    ctx["log_offset"] = 0
    await go("logs")


def graph(pts, key, minutes):
    maximum = max([1] + [p[key] for p in pts])
    t.small("最大目盛 " + str(maximum))
    with t.div(classes="time-chart", aria_label="時間帯別の" + MEASURES[key]):
        for p in pts:
            label = p["at"][:16] + " UTC · " + str(p[key])
            t.button(
                "",
                type="button",
                title=label,
                aria_label=label,
                classes="time-bar",
                style=f"--height:{100 * p[key] / maximum:.2f}%",
                on_click=action(inspect_bucket, p["at"], minutes),
            )
    with t.div(classes="chart-axis"):
        for p in (pts[0], pts[len(pts) // 2], pts[-1]):
            t.span(p["at"][5:16].replace("T", " "))


def metrics_view():
    if "workspace" in ctx and "dims" in ctx:
        filters_view(True)
    data = ctx.get("metrics")
    if data is None:
        t.p("メトリクスを取得できませんでした。")
        btn("メトリクスを再読み込み", load)
        return
    key = ctx["filters"]["measure"]
    pts = data["points"]
    with t.section(classes="box"):
        t.h2(MEASURES[key])
        t.p(
            data["start"][:16].replace("T", " ") + " ～ " + data["end"][:16].replace("T", " ") + " UTC",
            classes="muted",
        )
        if not any(p["calls"] for p in pts):
            t.p("この期間に呼び出しの記録はありません。")
        else:
            graph(pts, key, data["minutes"])
        with t.details():
            t.summary("データを表で確認")
            with t.div(classes="table-scroll"), t.table():
                with t.thead(), t.tr():
                    for title in ("期間の開始（UTC）", MEASURES[key], "記録"):
                        t.th(title)
                with t.tbody():
                    for p in pts:
                        with t.tr():
                            t.td(p["at"][:16].replace("T", " "))
                            t.td(str(p[key]))
                            with t.td():
                                btn("ログを見る", inspect_bucket, p["at"], data["minutes"])


async def download_logs():
    params = {**time_params(), "request_id": ctx.get("access_id", "")}
    parts = window.Array.new()
    while True:
        res = await pyfetch(
            client.prefix + "/access-logs/download?" + urlencode(params),
            headers={"Authorization": "Bearer " + str(client.store.getItem("access"))},
        )
        if not res.ok:
            raise ValueError("ログを取得できませんでした")
        parts.push(await res.js_response.blob())
        cursor = res.js_response.headers.get("x-next-cursor")
        if not cursor:
            break
        params["cursor"] = str(cursor)
    save_blob(window.Blob.new(parts), "access-log.jsonl")


async def download_audit():
    parts = window.Array.new()
    params = {
        "action": ctx["audit_action"],
        "request_id": ctx["audit_id"],
        "limit": 250,
        "until": datetime.now(timezone.utc).isoformat(),
    }
    offset = 0
    while True:
        rows = await client.api("/audit?" + urlencode({**params, "offset": offset}))
        parts.push("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        if len(rows) < 250:
            break
        offset += len(rows)
    save_blob(window.Blob.new(parts), "audit-log.jsonl")


def save_blob(blob, filename):
    url = window.URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)


async def log_lookup():
    ctx.update(access_id=value("access-id"), log_offset=0)
    await load()


async def log_page(offset):
    ctx["log_offset"] = offset
    await load()


def logs_view():
    filters_view(False)
    with t.div(classes="box"):
        field("照合するリクエストID", "access-id", text=ctx.get("access_id", ""))
        with t.div(classes="btn-grouping"):
            btn("IDで検索", log_lookup)
            btn("アクセスログをダウンロード", download_logs)
    rows = ctx["log_rows"]
    if not rows:
        t.p("条件に一致するアクセスログはありません。", classes="empty")
    for row in rows:
        with t.article(classes="audit-row"):
            t.strong(f"{row['status']}　{row['method']} {row['operation']}")
            t.p(
                f"{row['at'][:19]} UTC　{row['actor']}　{row['project']}　{row['environment']}　{row['duration_ms']} ms"
            )
            t.small("リクエストID　" + row["request_id"], classes="mono")
            if row.get("key_id"):
                t.small("キーID　" + row["key_id"], classes="mono")
            btn("対応する業務監査", trace_lookup, row["request_id"])
    if ctx.get("log_offset", 0):
        btn("前の50件", log_page, ctx["log_offset"] - 50)
    if len(rows) == 50:
        btn("次の50件", log_page, ctx.get("log_offset", 0) + 50)


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


def alerts_view():
    if target_options():
        with t.div(classes="box"):
            t.h2("利用件数のルール")
            field("対象の利用申請", "alert-target", options=target_options())
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
    for r in ctx["rules"]:
        with t.article(classes="box"):
            t.h3(r["name"] + " · " + r["project"] + " · " + LABEL[r["environment"]])
            t.p(
                f"{r['minutes']}分 / {r['threshold']}件　現在 {r['calls']}件　"
                + ("無効" if not r["enabled"] else "通知と停止" if r["stop"] else "通知")
            )
    if not ctx["rules"]:
        t.p("設定済みのルールはありません。", classes="empty")


async def delete_listing(asset):
    if window.confirm(asset["name"] + "を削除し、既存の利用権も終了しますか？"):
        await client.api("/apis/" + asset["id"] + "?revision=" + str(asset["revision"]), "DELETE")
        await go("inventory")
        ctx["message"] = "APIを削除しました"


@app.page()
class Portal(Page):
    def populate(self):
        user, page = ctx["me"], route()
        title = PAGES.get(
            page,
            "APIの詳細"
            if page.startswith("api/")
            else "掲載内容を編集"
            if page.startswith("edit/")
            else "APIを登録",
        )
        guide_detail = page.startswith("guide/")
        if guide_detail:
            guide = guide_views.BY_ID.get(page.split("/", 1)[1])
            title = guide.title if guide else "使い方ガイド"
        nav_open = ctx.get("nav_open", not window.matchMedia("(max-width: 780px)").matches)
        with t.header(classes="mast"):
            with t.div(classes="identity"):
                t.span("", classes="brand-mark", aria_hidden="true")
                t.strong("継手API", classes="brand")
                t.span("APIポータル", classes="product")
            if user:
                with t.form(classes="global-search", on_submit=action(global_search)):
                    t.input(
                        id="global-query",
                        type="search",
                        placeholder="APIカタログを検索",
                        aria_label="すべての公開APIを検索",
                    )
            with t.label(classes="mode-control"):
                t.span("表示", classes="mode-label")
                with t.select(aria_label="表示モード", on_change=theme_changed):
                    for key, label in (("auto", "端末設定"), ("light", "ライト"), ("dark", "ダーク")):
                        t.option(
                            label,
                            value=key,
                            selected=key == (window.localStorage.getItem("visual-mode") or "auto"),
                        )
            if user:
                with t.button(
                    type="button",
                    classes="bell-button",
                    aria_label="通知を開く（未読" + str(ctx["badge"]) + "件）",
                    on_click=action(go, "notifications"),
                ):
                    t.span("", classes="bell-icon", aria_hidden="true")
                    t.strong(str(ctx["badge"]) if ctx["badge"] else "", id="unread-count")
                t.span(
                    " / ".join(sorted(set(user["owners"] + user["projects"]))) or role_title(),
                    classes="project",
                )
                btn("ログアウト", logout)
        if not ctx["config"] or not user:
            with t.section(classes="login box"):
                if ctx["message"]:
                    t.div(
                        ctx["message"],
                        role="alert" if ctx["error"] else "status",
                        classes="notice error" if ctx["error"] else "notice",
                    )
                if ctx["config"]:
                    login_page()
                else:
                    t.p("カタログを読み込み中…")
            return
        with t.div(classes="console-tools"):
            with t.button(
                type="button",
                id="nav-toggle",
                classes="menu-button",
                aria_label="ナビゲーション",
                aria_controls="portal-nav",
                aria_expanded="true" if nav_open else "false",
                on_click=toggle_navigation,
            ):
                t.span("", classes="menu-icon", aria_hidden="true")
            with t.div(classes="crumb", aria_label="現在地"):
                t.a("継手API", href="#/home")
                t.span("›", aria_hidden="true")
                t.strong(title)
            if page != "guide" and not guide_detail:
                t.a(
                    "使い方ガイド",
                    href="#/guide",
                    classes="guide-shortcut",
                    on_click=action(go, "guide"),
                )
        with t.div(id="workspace", classes="workspace", data_nav="open" if nav_open else "closed"):
            with t.nav(id="portal-nav", classes="rail", aria_label="ポータル"):
                t.strong("継手API", classes="rail-title")
                for label, pages in [
                    (
                        "ワークスペース",
                        ("home", "catalog", "keys", "mine", "notifications", "workspace", "dashboard"),
                    ),
                    ("ヘルプ", ("guide", "inquiries")),
                    ("管理", ("members",)),
                    ("提供者メニュー", ("inventory", "inbox")),
                    ("ガバナンス", ("metrics", "logs", "alerts", "audit")),
                ]:
                    if label == "管理" and not user["admin"]:
                        continue
                    if label == "提供者メニュー" and not (user["owners"] or user["leads"]):
                        continue
                    with t.div(classes="nav-group"):
                        t.small(label)
                        for target in pages:
                            if target == "inventory" and not user["owners"]:
                                continue
                            active = (
                                page == target
                                or (page == "register" and target == "inventory")
                                or (guide_detail and target == "guide")
                            )
                            t.button(
                                PAGES[target],
                                type="button",
                                classes="nav-item active" if active else "nav-item",
                                aria_current="page" if active else "false",
                                on_click=action(go, target),
                            )
            with t.section(classes="content"):
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
                if page == "home":
                    chat_views.home(ctx, render)
                elif page == "dashboard":
                    dashboard_view()
                elif page == "inquiries":
                    chat_views.inquiries(ctx, btn, reply_inquiry, inquiry_page)
                elif page == "guide":
                    guide_views.index(ctx)
                elif guide_detail:
                    guide_views.article(page.split("/", 1)[1], user, PAGES, go, btn)
                elif page == "workspace":
                    workspace_views.workspace_view(ctx, field, btn, load)
                elif page == "keys":
                    workspace_views.keys_view(ctx, field, btn, load)
                elif page == "members" and user["admin"]:
                    members_view()
                elif page == "notifications":
                    notices_view()
                elif page == "metrics":
                    metrics_view()
                elif page == "logs":
                    logs_view()
                elif page == "alerts":
                    alerts_view()
                elif page.startswith("edit/") and user["owners"]:
                    inventory_form(ctx["detail"])
                elif page in ("catalog", "inventory"):
                    cards()
                elif page == "register" and user["owners"]:
                    inventory_form()
                elif page in ("mine", "inbox"):
                    rights_page(page == "inbox")
                elif page == "audit":
                    audit_view()


async def poll_badge():
    while True:
        await asyncio.sleep(30)
        if not ctx["me"] or ctx["busy"] or document.hidden:
            continue
        try:
            count = (await client.api("/notifications/count"))["unread"]
            indicator = document.getElementById("unread-count")
            if indicator:
                ctx["badge"] = count
                indicator.textContent = str(count) if count else ""
                indicator.parentElement.setAttribute("aria-label", f"通知を開く（未読{count}件）")
        except Exception:
            continue


async def start():
    document.documentElement.setAttribute(
        "data-mode", window.localStorage.getItem("visual-mode") or "auto"
    )
    client.prefix = (await (await pyfetch("/entry.json")).json())["api_prefix"]
    ctx["config"] = await client.api("/config")
    await client.callback(ctx["config"])
    if client.store.getItem("access"):
        await refresh_session()


add_event_listener(window.matchMedia("(max-width: 780px)"), "change", adapt_navigation)
add_event_listener(window, "popstate", action(load))
render()
asyncio.ensure_future(run(start))

asyncio.ensure_future(poll_badge())
