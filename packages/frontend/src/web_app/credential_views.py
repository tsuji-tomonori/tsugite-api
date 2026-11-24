"""Portal controls for access-token lifetime, authentication methods and credential grants."""

import json
from urllib.parse import quote, urlencode

import client
from js import document, window
from list_layout import disclosure, result_table
from puepy import t

MODES = {
    "bearer": "短期Bearer",
    "app": "アプリ（ユーザー委任）",
    "system": "システム（無人実行）",
}


def val(identifier):
    return str(document.getElementById(identifier).value).strip()


def number(label, identifier, initial, low, high, placeholder="", on_change=None):
    attrs = {"on_change": on_change} if on_change else {}
    with t.label(classes="field"):
        t.span(label, id=identifier + "-label")
        t.input(
            id=identifier,
            classes="form-control",
            type="number",
            min=low,
            max=high,
            step=1,
            value=str(initial),
            placeholder=placeholder,
            aria_labelledby=identifier + "-label",
            **attrs,
        )


def minutes(identifier, label, low, high):
    try:
        value = int(val(identifier))
    except ValueError:
        raise client.InputError(label + "は分単位の整数で指定してください") from None
    if not low <= value <= high:
        raise client.InputError(f"{label}は{low}～{high}分で選んでください")
    return value


def limit_view(ctx, field, btn, reload, *, kind, identifier):
    me = ctx["me"]["subject"]
    endpoint = "/credential-limits/" + kind + "/" + quote(identifier, safe="")
    state = ctx.get("credential_limit", {})
    prefix = "token-limit-" + kind + "-" + identifier

    async def open_limit():
        data = await client.api(endpoint)
        ctx["credential_limit"] = {"owner": me, "endpoint": endpoint, "data": data}

    async def save():
        value = val(prefix)
        max_minutes = (
            minutes(prefix, "有効期限の上限", 1, decision["inherited_minutes"]) if value else None
        )
        await client.api(endpoint, "PUT", {"max_minutes": max_minutes})
        await open_limit()
        await reload()
        ctx["message"] = "有効期限の上限を保存しました"

    async def close():
        ctx.pop("credential_limit", None)

    if state.get("endpoint") != endpoint or state.get("owner") != me:
        btn("アクセストークンの上限を設定", open_limit)
        return
    decision = state["data"]
    upper = decision["inherited_minutes"]
    t.h3("アクセストークンの有効期限")
    t.p(f"上位設定の上限　{upper}分")
    number(
        "この範囲の上限（分）",
        prefix,
        decision.get("max_minutes") or "",
        1,
        upper,
        "空欄で上位設定を継承",
    )
    with t.div(classes="btn-grouping"):
        btn("有効期限の上限を保存", save, primary=True)
        btn("設定を閉じる", close)


def checked(identifier):
    return bool(document.getElementById(identifier).checked)


def checkbox(identifier, label, *, on_change=None, selected=False):
    attrs = {"on_change": on_change} if on_change else {}
    with t.label(classes="compact-row"):
        t.input(type="checkbox", id=identifier, checked=selected, **attrs)
        t.span(label)


def choose(label, identifier, choices, on_change=None):
    with t.label(classes="field"):
        t.span(label)
        attrs = {"on_change": on_change} if on_change else {}
        with t.select(id=identifier, classes="form-select", aria_label=label, **attrs):
            for name, title in choices:
                t.option(title, value=name)


def render_form(ctx, project, options, field, btn, reload):
    assets = options["assets"]
    members = options["members"]
    cap = int(options["max_minutes"])
    personal = project == ctx["me"].get("personal_project")
    modes = dict(MODES)
    if personal or not options["may_manage"]:
        modes.pop("system")

    def selected_indexes():
        return [i for i in range(len(assets)) if checked(f"cred-api-{i}")]

    def current_limit():
        if val("cred-scope") != "selected":
            return cap
        return min((assets[i]["max_minutes"] for i in selected_indexes()), default=cap)

    def sync(event):
        mode = val("cred-mode")
        restricted = val("cred-scope") == "selected"
        for code in modes:
            document.getElementById("cred-note-" + code).hidden = code != mode
        kind = document.getElementById("cred-kind")
        if mode == "system":
            kind.value = "shared"
        kind.disabled = mode == "system" or personal
        document.getElementById("cred-api-list").hidden = not restricted
        for i in range(len(assets)):
            document.getElementById(f"cred-detail-{i}").hidden = not checked(f"cred-api-{i}")
            is_limited = val(f"cred-actions-{i}") == "selected"
            document.getElementById(f"cred-ops-{i}").hidden = not is_limited
        allow_people = mode == "app" and str(kind.value) == "shared"
        document.getElementById("cred-people").hidden = not allow_people
        document.getElementById("cred-user-list").hidden = val("cred-user-scope") != "selected"
        maximum = current_limit()
        document.getElementById("cred-ttl").max = str(maximum)
        document.getElementById(
            "cred-policy-cap"
        ).textContent = f"この範囲で選べる有効期限　最長{maximum}分"

    async def issue():
        if val("credential-project") != project:
            raise client.InputError("変更先のプロジェクトで発行条件を確認してください")
        mode = val("cred-mode")
        kind = "shared" if mode == "system" else val("cred-kind")
        ttl = minutes("cred-ttl", "有効期限", 1, current_limit())
        refresh = minutes("cred-refresh", "更新開始", 1, ttl)
        selected = selected_indexes() if val("cred-scope") == "selected" else []
        if not selected and val("cred-scope") == "selected":
            raise client.InputError("対象APIを1件以上選んでください")
        operations = {}
        for i in selected:
            if val(f"cred-actions-{i}") == "selected":
                ids = [s for k, s in enumerate(assets[i]["operations"]) if checked(f"cred-op-{i}-{k}")]
                if not ids:
                    raise client.InputError(assets[i]["name"] + "の操作を1件以上選んでください")
                operations[assets[i]["id"]] = ids
        people = []
        if mode == "app" and kind == "shared" and val("cred-user-scope") == "selected":
            people = [r["subject"] for i, r in enumerate(members) if checked(f"cred-user-{i}")]
            if not people:
                raise client.InputError("利用者を1人以上選んでください")
        if not val("cred-name"):
            raise client.InputError("認証情報の名前を入力してください")
        result = await client.api(
            "/credentials",
            "POST",
            {
                "name": val("cred-name"),
                "project": project,
                "kind": kind,
                "mode": mode,
                "ttl_minutes": ttl,
                "refresh_minutes": refresh,
                "api_ids": [assets[i]["id"] for i in selected],
                "operations": operations,
                "users": people,
            },
        )
        remember(ctx, result, mode)
        ctx.pop("credential_options", None)
        await reload()
        ctx["message"] = "認証情報を発行しました"

    t.h3("認証方式と利用条件")
    field("認証情報の名前", "cred-name", placeholder="例　棚卸アプリ")
    choose("認証方式", "cred-mode", modes.items(), sync)
    notes = {
        "bearer": "発行したトークンをBearerとしてすぐに使えます。有効期間中は値を持つ人が呼び出せます。",
        "app": "アプリのクライアント認証情報と利用者のログイン情報で、本人に許可した操作のトークンを取得します。",
        "system": "クライアント認証情報は失効させるまで利用でき、無人ジョブが必要なときにアクセストークンを取得します。",
    }
    for code in modes:
        t.p(notes[code], id="cred-note-" + code, classes="muted", hidden=code != "bearer")
    choose(
        "認証情報の所有者",
        "cred-kind",
        [("personal", "本人")] if personal else [("personal", "本人"), ("shared", "プロジェクト")],
        sync,
    )
    choose(
        "対象APIの選び方",
        "cred-scope",
        [("all", "利用を承認されたすべてのAPI"), ("selected", "APIと操作を選ぶ")],
        sync,
    )
    with t.div(id="cred-api-list", hidden=True):
        for i, asset in enumerate(assets):
            checkbox(f"cred-api-{i}", asset["name"], on_change=sync)
            with t.div(id=f"cred-detail-{i}", hidden=True):
                choose(
                    asset["name"] + "で許可する操作",
                    f"cred-actions-{i}",
                    [("all", "すべての操作"), ("selected", "操作を指定")],
                    sync,
                )
                with t.div(id=f"cred-ops-{i}", hidden=True):
                    for j, op in enumerate(asset["operations"]):
                        checkbox(f"cred-op-{i}-{j}", op)
        if not assets:
            t.p("選択できるAPIがありません。")
    with t.div(id="cred-people", hidden=True):
        choose(
            "アプリを利用できる人",
            "cred-user-scope",
            [("all", "対象プロジェクトの利用者"), ("selected", "利用者を指定")],
            sync,
        )
        with t.div(id="cred-user-list", hidden=True):
            for i, r in enumerate(members):
                checkbox(f"cred-user-{i}", r["username"])
    maximum = cap
    t.p(f"この範囲で選べる有効期限　最長{maximum}分", id="cred-policy-cap")
    if options.get("limits"):
        with t.details():
            t.summary("有効期限を制限している設定")
            for limit in options["limits"]:
                t.p(f"{limit['name']}　{limit['minutes']}分")
    default_ttl = min(60, maximum)

    def ttl_changed(event):
        raw = str(event.target.value)
        refresh = document.getElementById("cred-refresh")
        if raw.isdecimal() and int(raw) > 0:
            refresh.max = raw

    number("トークンの有効期限（分）", "cred-ttl", default_ttl, 1, maximum, on_change=ttl_changed)
    number("更新を開始できる経過時間（分）", "cred-refresh", max(1, default_ttl - 5), 1, default_ttl)
    t.p(
        "更新開始は発行からの経過時間です。指定時間を過ぎて次に取得すると、新しいトークンが発行されます。",
        classes="muted",
    )
    btn("認証情報を発行", issue, primary=True)


def remember(ctx, result, mode):
    ctx["issued_key"] = {
        "subject": ctx["me"]["subject"],
        "mode": mode,
        "client_id": result.get("client_id"),
        "token": result.get("access_token"),
        "secret": result.get("client_secret"),
        "expires_in": result.get("expires_in"),
        "refresh_after": result.get("refresh_after"),
    }


def credentials_view(ctx, field, btn, reload, projects):
    owner = ctx["me"]["subject"]
    secret = ctx.get("issued_key") or {}

    async def clear():
        ctx.pop("issued_key", None)

    async def copy(value):
        await window.navigator.clipboard.writeText(value)
        ctx["message"] = "コピーしました"

    if secret.get("mode") and secret.get("subject") == owner:
        with t.section(classes="box"):
            t.h2("発行した認証情報")
            if secret.get("client_id"):
                t.p(
                    "クライアントID　" + secret["client_id"],
                    classes="mono",
                    id="credential-value-client-id",
                )
            for label, k in (("アクセストークン", "token"), ("クライアントシークレット", "secret")):
                if secret.get(k):
                    t.h3(label)
                    t.code(secret[k], classes="code", id="credential-value-" + k)
                    btn(label + "をコピー", copy, secret[k])
            if secret.get("token") and isinstance(secret.get("expires_in"), int):
                t.p(f"取得時点の残り有効時間　{secret['expires_in']}秒")
                if isinstance(secret.get("refresh_after"), int):
                    t.p(f"次回更新まで　{secret['refresh_after']}秒")
            t.p("この表示を閉じる前に、必要な値を保管してください。")
            btn("秘密の表示を閉じる", clear)
    named = dict(projects)
    opts = ctx.get("credential_options", {})
    loaded = opts.get("owner") == owner and opts.get("project") in named

    async def prepare():
        selected = val("credential-project")
        response = await client.api("/credentials/options?" + urlencode({"project": selected}))
        ctx["credential_options"] = {"owner": owner, "project": selected, "data": response}
        ctx.pop("issued_key", None)

    modern = [r for r in ctx.get("keys", []) if r.get("mode") in MODES]
    with t.div(classes="list-tools"):
        if modern:
            t.h2("認証情報一覧")
        if projects:
            with disclosure("認証情報を作成", expanded=loaded):
                field(
                    "発行先プロジェクト",
                    "credential-project",
                    options=projects,
                    text=opts["project"] if loaded else "",
                )
                btn("発行条件を確認", prepare)
                if loaded:
                    t.p("発行先　" + named[opts["project"]], classes="muted")
                    render_form(ctx, opts["project"], opts["data"], field, btn, reload)

    if not modern:
        return
    directory = ctx["workspace"]
    names = {a["id"]: a["name"] for a in ctx.get("key_assets", [])}

    async def obtain(row):
        result = await client.api("/credentials/" + quote(row["id"], safe="") + "/token", "POST")
        remember(ctx, result, row["mode"])
        await reload()

    async def rotate(row):
        if window.confirm(row["name"] + " のクライアントシークレットを更新しますか？"):
            result = await client.api("/credentials/" + quote(row["id"], safe="") + "/rotate", "POST")
            remember(ctx, result, row["mode"])
            await reload()

    async def revoke(row):
        if window.confirm(row["name"] + " を失効しますか？"):
            await client.api("/keys/" + quote(row["id"], safe=""), "DELETE")
            ctx.pop("issued_key", None)
            await reload()
            ctx["message"] = "認証情報を失効しました"

    users = {u["subject"]: u["username"] for u in directory.get("users", [])}
    with result_table("認証情報一覧", ("名前", "認証方式・所有者・状態", "有効期限・利用範囲", "操作")):
        for row in modern:
            with t.tr():
                t.th(row["name"], scope="row")
                t.td(
                    MODES[row["mode"]]
                    + " · "
                    + named.get(row["project"], row["project"])
                    + " · "
                    + ("本人" if row["kind"] == "personal" else "プロジェクト共有")
                    + " · "
                    + ("失効済み" if row["revoked"] else "有効")
                )
                with t.td():
                    t.p(
                        f"トークン有効期限 {row['ttl_minutes']}分　更新開始 {row['refresh_minutes']}分後"
                    )
                    for asset in row["api_ids"]:
                        ops = row.get("operations", {}).get(asset)
                        scope = (
                            "すべての操作" if ops is None else ("、".join(ops) or "許可された操作なし")
                        )
                        t.p(names.get(asset, asset) + "　" + scope)
                    if not row["api_ids"]:
                        t.p("利用を承認されたすべてのAPI")
                    if row["mode"] in ("system", "app"):
                        t.p("クライアントID　" + (row.get("client_id") or row["id"]), classes="mono")
                    if row.get("users"):
                        t.p("利用者　" + "、".join(users.get(s, s) for s in row["users"]))
                with t.td():
                    manager = (
                        directory["admin"]
                        or row["creator"] == owner
                        or row["kind"] == "shared"
                        and row["project"] in directory["leads"]
                    )
                    if not row["revoked"]:
                        with t.details():
                            t.summary("トークンの取得と呼び出し方")
                            if row["mode"] == "bearer":
                                t.p(
                                    "取得・更新ボタンでトークンを取得できます。外部から更新する場合は、本人のログイントークンをヘッダーに指定します。"
                                )
                                t.pre(
                                    f"POST {client.prefix}/credentials/{row['id']}/token\nAuthorization: Bearer <ログイントークン>",
                                    classes="code",
                                )
                            else:
                                t.p("アプリまたはジョブのサーバーからトークン発行先に送信します。")
                                request_headers = "Content-Type: application/json"
                                if row["mode"] == "app":
                                    request_headers += (
                                        "\nAuthorization: Bearer <利用者のログイントークン>"
                                    )
                                payload = {
                                    "client_id": row.get("client_id") or row["id"],
                                    "client_secret": "<保管したクライアントシークレット>",
                                }
                                t.pre(
                                    f"POST {client.prefix}/auth/token\n{request_headers}\n\n"
                                    + json.dumps(payload, ensure_ascii=False, indent=2),
                                    classes="code",
                                )
                            t.p("APIを呼び出す際は、取得したアクセストークンを指定します。")
                            t.pre("Authorization: Bearer <アクセストークン>", classes="code")
                        with t.div(classes="btn-grouping"):
                            if (
                                (
                                    row["project"] in ctx["me"]["projects"]
                                    or row["project"] == ctx["me"].get("personal_project")
                                )
                                and (row["kind"] == "shared" or row["creator"] == owner)
                                and (not row.get("users") or owner in row["users"])
                                and (
                                    row["mode"] != "system"
                                    or directory["admin"]
                                    or row["project"] in directory["leads"]
                                )
                            ):
                                btn("アクセストークンを取得・更新", obtain, row)
                            leader = directory["admin"] or row["project"] in directory["leads"]
                            creator_can_rotate = (
                                row["mode"] == "app"
                                and row["creator"] == owner
                                and (not row.get("users") or owner in row["users"])
                            )
                            if row["mode"] in ("app", "system") and (leader or creator_can_rotate):
                                btn("シークレットを更新", rotate, row)
                            if manager:
                                btn("認証情報を失効", revoke, row)
