# OpenAPIの仕様と認証付き実行フォームを表示する。
from __future__ import annotations

import asyncio
import json
import shlex
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from urllib.parse import quote, unquote, urlencode

from apis import access as access_api
from apis import client
from apis.invocation import CREDENTIAL_MODES, credential_headers, fetch
from content.openapi_fields import parameters, resolve
from js import document, window
from puepy import t
from routing.audit_navigation import trace_lookup
from runtime.portal_ui import action

METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
INVOKABLE = frozenset(("get", "post", "put", "patch", "delete"))
ENVIRONMENTS = {"sandbox": "検証", "staging": "準本番", "production": "本番"}


def type_name(spec: dict[str, Any], schema: dict[str, Any]) -> str:
    """スキーマの型を表示用に整える。"""
    schema = resolve(spec, schema)
    if not isinstance(schema, dict):
        return "任意" if schema else "許可なし"
    kind = schema.get("type")
    if isinstance(kind, list):
        return " / ".join(kind)
    if kind == "array":
        items = schema.get("items", {})
        name = items.get("$ref", "").split("/")[-1] if isinstance(items, dict) else ""
        return "array[" + (name or type_name(spec, items)) + "]"
    for group in ("oneOf", "anyOf", "allOf"):
        if group in schema:
            return group
    return str(kind or ("object" if "properties" in schema else "任意"))


def data_schema(spec: dict[str, Any], media: dict[str, Any]) -> None:
    """データスキーマを描画する。"""
    schema = media.get("schema")
    if schema is not None:
        t.pre(json.dumps(resolve(spec, schema), ensure_ascii=False, indent=2), classes="code")


def media_docs(spec: dict[str, Any], content: dict[str, Any]) -> None:
    """メディア形式ごとの仕様を描画する。"""
    for media_type, media in content.items():
        if not isinstance(media, dict):
            continue
        with t.details():
            t.summary(media_type + " のスキーマ")
            data_schema(spec, media)


def available_bindings(
    asset_id: str, rights: list[dict[str, Any]], keys: list[dict[str, Any]], subject: str
) -> list[tuple[dict[str, Any], str, str, str]]:
    """利用可能な認証情報と環境を組み合わせる。"""
    options = []
    seen = set()
    for key in keys:
        if key.get("mode") not in CREDENTIAL_MODES:
            continue
        if key.get("revoked") or key.get("revoked_at") or not key.get("can_portal_exchange", True):
            continue
        if key.get("api_ids") and asset_id not in key["api_ids"]:
            continue
        if key.get("users") and subject not in key["users"]:
            continue
        personal = key["kind"] == "personal"
        if personal and key.get("creator") != subject:
            continue
        for grant in rights:
            if (
                grant["asset_id"] != asset_id
                or grant["status"] != "approved"
                or grant["project"] != key["project"]
                or grant.get("subject")
                and (not personal or grant["subject"] != subject)
            ):
                continue
            key_env = key["id"], grant["environment"]
            if key_env in seen:
                continue
            seen.add(key_env)
            env = grant["environment"]
            label = f"{key['name']}（{'個人' if personal else '共有'}） · {key['project']} · {ENVIRONMENTS.get(env, env)}"
            if mode := CREDENTIAL_MODES.get(key.get("mode", "")):
                label += " · " + mode
            options.append((key, env, key["project"], label))
    return options


def approved_rights(
    asset: dict[str, Any], rights: list[dict[str, Any]], subject: str
) -> list[dict[str, Any]]:
    """対象者の承認済み申請を抽出する。"""
    return [
        grant
        for grant in rights
        if grant["asset_id"] == asset["id"]
        and grant["status"] == "approved"
        and grant["environment"] in asset["environments"]
        and grant.get("subject") in (None, "", subject)
    ]


def trial_bindings(
    rights: list[dict[str, Any]], personal_project: str
) -> list[tuple[dict[str, Any] | None, str, str, str]]:
    """試行できるプロジェクトと環境を列挙する。"""
    options = {}
    for grant in rights:
        project, env = grant["project"], grant["environment"]
        label = "個人利用" if project == personal_project else project
        options[(project, env)] = (None, env, project, f"{label} · {ENVIRONMENTS.get(env, env)}")
    return list(options.values())


def trial_key_issuer(asset: dict[str, Any]) -> Callable[[str], Awaitable[dict[str, Any]]]:
    """同じプロジェクトの試行用認証情報を再利用する発行関数を作る。"""
    keys = {}
    lock = asyncio.Lock()

    async def issue(project: str) -> dict[str, Any]:
        async with lock:
            if project not in keys:
                keys[project] = await access_api.issue(
                    {
                        "name": ("API Docs · " + asset["name"])[:120],
                        "project": project,
                        "kind": "personal",
                        "mode": "bearer",
                        "api_ids": [asset["id"]],
                        "ttl_minutes": 1,
                    }
                )
            return keys[project]

    return issue


def value(element_id: str) -> str:
    """入力要素の値を読み取る。"""
    return str(document.getElementById(element_id).value)


def param_values(spec: dict[str, Any], param: dict[str, Any], value_text: str) -> Any:
    """入力値をOpenAPIの型に変換する。"""
    schema = resolve(spec, param.get("schema", {}))
    kind = schema.get("type") if isinstance(schema, dict) else ""
    if kind in ("array", "object"):
        try:
            data = json.loads(value_text)
        except ValueError as exc:
            raise client.InputError(f"{param['name']} はJSONで指定してください") from exc
        if not isinstance(data, list if kind == "array" else dict):
            raise client.InputError(f"{param['name']} の型は {kind} です")
        return data
    return value_text


def stringify(value: object) -> str:
    """値を送信用の文字列に整える。"""
    return (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )


def build_location(
    spec: dict[str, Any], path: str, params: list[dict[str, Any]], entered: dict[int, str]
) -> str:
    """パスとクエリをOpenAPIの規則で組み立てる。"""
    decoded_path = unquote(path)
    if (
        not path.startswith("/")
        or any(c in decoded_path for c in ("?", "#", "\\"))
        or any(p in (".", "..") for p in decoded_path.split("/"))
        or any(ord(c) < 32 for c in decoded_path)
    ):
        raise client.InputError("この操作パスをポータルから呼び出すことはできません")
    query: list[tuple[str, str]] = []
    for i, param in enumerate(params):
        where, name = param["in"], param["name"]
        if where not in ("path", "query"):
            continue
        text = entered.get(i, "")
        if text == "":
            if where == "path" or param.get("required"):
                raise client.InputError(f"{name} を入力してください")
            continue
        data = param_values(spec, param, text)
        style = param.get("style", "form" if where == "query" else "simple")
        explode = param.get("explode", style == "form")
        seq = [stringify(v) for v in data] if isinstance(data, list) else []
        pairs = [(k, stringify(v)) for k, v in data.items()] if isinstance(data, dict) else []
        if where == "path":
            if style != "simple":
                raise client.InputError("この操作の実行には simple 形式のパスパラメータが必要です")
            if isinstance(data, list):
                encoded = ",".join(quote(v, safe="") for v in seq)
            elif isinstance(data, dict):
                sep = "=" if explode else ","
                encoded = ",".join(quote(k, safe="") + sep + quote(v, safe="") for k, v in pairs)
            else:
                encoded = quote(stringify(data), safe="")
            if encoded in (".", ".."):
                raise client.InputError(f"{name} の値を確認してください")
            path = path.replace("{" + name + "}", encoded)
        elif isinstance(data, dict) and style == "deepObject":
            query.extend((f"{name}[{k}]", v) for k, v in pairs)
        elif isinstance(data, dict) and style == "form" and explode:
            query.extend(pairs)
        elif isinstance(data, list) and style == "form" and explode:
            query.extend((name, v) for v in seq)
        else:
            sep = {"pipeDelimited": "|", "spaceDelimited": " "}.get(style, ",")
            items = [s for pair in pairs for s in pair] if isinstance(data, dict) else seq
            query.append((name, sep.join(items) if isinstance(data, (list, dict)) else stringify(data)))
    if "{" in path or "}" in path:
        raise client.InputError("必要なパスパラメータが仕様に定義されていません")
    return path + ("?" + urlencode(query) if query else "")


def option_list(label: str, element_id: str, choices: Sequence[tuple[str, str]]) -> None:
    """ラベル付きの選択欄を表示する。"""
    with t.label(classes="field"):
        t.span(label)
        with t.select(id=element_id, classes="form-select", aria_label=label):
            for key, text in choices:
                t.option(text, value=key)


def input_param(spec: dict[str, Any], param: dict[str, Any], element_id: str) -> None:
    """パラメーターの入力欄を表示する。"""
    schema = resolve(spec, param.get("schema", {}))
    sample = param.get("example")
    if sample is None and isinstance(schema, dict):
        sample = schema.get("example", schema.get("default"))
    with t.label(classes="field"):
        required = param["in"] == "path" or param.get("required", False)
        t.span(param["name"] + "（" + param["in"] + "）" + (" 必須" if required else " 任意"))
        t.input(
            id=element_id,
            classes="form-control",
            required=required,
            placeholder=stringify(sample) if sample is not None else type_name(spec, schema),
        )


def curl_command(url: str, options: dict[str, Any]) -> str:
    """実行内容を再現するcurlコマンドを作る。"""
    args = ["curl", "--globoff", "--request", shlex.quote(options["method"]), "--url", shlex.quote(url)]
    for name, val in options["headers"].items():
        header = (
            '"Authorization: Bearer ${ACCESS_TOKEN}"'
            if name.lower() == "authorization"
            else shlex.quote(f"{name}: {val}")
        )
        args.extend(["--header", header])
    if "body" in options:
        args.extend(["--data-raw", shlex.quote(options["body"])])
    return " ".join(args)


def try_operation(
    spec: dict[str, Any],
    asset: dict[str, Any],
    bindings: Sequence[tuple[dict[str, Any] | None, str, str, str]],
    method: str,
    path: str,
    params: list[dict[str, Any]],
    body: dict[str, Any],
    prefix: str,
    *,
    binding_label: str = "利用する認証情報と環境（必須）",
    submit_label: str = "認証して実行",
    issue_key: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
) -> None:
    """認証・送信・応答の操作欄を表示する。"""
    choices = [(str(i), b[3]) for i, b in enumerate(bindings)]
    if issue_key and len(choices) > 1:
        choices.insert(0, ("", "選んでください"))
    option_list(
        binding_label,
        prefix + "-key",
        choices,
    )
    for i, param in enumerate(params):
        if param["in"] in ("query", "path"):
            input_param(spec, param, prefix + f"-param-{i}")
    content = body.get("content", {})
    if content:
        option_list("本文の形式（本文送信時は必須）", prefix + "-media", [(k, k) for k in content])
        with t.label(classes="field"):
            t.span("送信するリクエスト本文" + ("（必須）" if body.get("required") else "（任意）"))
            t.textarea(id=prefix + "-body", classes="form-control", required=bool(body.get("required")))

    async def send(button: Any, out: Any) -> None:
        try:
            selected = value(prefix + "-key")
            if not selected:
                raise client.InputError("利用するプロジェクトと環境を選んでください")
            key, env, project, _ = bindings[int(selected)]
            entered = {
                i: value(prefix + f"-param-{i}")
                for i, p in enumerate(params)
                if p["in"] in ("query", "path")
            }
            location = build_location(spec, path, params, entered)
            headers: dict[str, str] = {}
            opts = {"method": method.upper(), "headers": headers, "redirect": "error"}
            if content:
                text = value(prefix + "-body")
                if not text and body.get("required"):
                    raise client.InputError("リクエスト本文を入力してください")
                if text:
                    media = value(prefix + "-media")
                    if media == "application/json" or media.endswith("+json"):
                        try:
                            json.loads(text)
                        except ValueError as exc:
                            raise client.InputError(
                                "リクエスト本文は正しいJSONで入力してください"
                            ) from exc
                    headers["Content-Type"] = media
                    opts["body"] = text
            if issue_key:
                key = await issue_key(project)
                if not button.isConnected:
                    return
            headers.update(await credential_headers(key))
            if not button.isConnected:
                return
            url = str(window.location.origin) + client.invocation_path(asset, env, project) + location
            document.getElementById(prefix + "-curl").textContent = curl_command(url, opts)
            document.getElementById(prefix + "-replay").hidden = False
            audit = document.getElementById(prefix + "-audit")
            result = await fetch(url, **opts)
            trace = result.headers.get("x-request-id", "")
            if trace:
                audit.dataset.trace = trace
                audit.hidden = False
            response = await result.string()
            if len(response) > 12000:
                response = response[:12000] + "\n（先頭12,000文字まで表示）"
            out.textContent = f"HTTP {result.status}\nリクエストID　{trace}\n{response}"
        except Exception as exc:
            client.report(
                exc,
                method.upper() + " " + path,
                route="/api/invoke/{key}/{environment}/{project}/{tail:path}",
            )
            out.textContent = str(exc)
        finally:
            button.disabled = False
            button.removeAttribute("aria-busy")
            button.textContent = submit_label

    def submit(event: Any) -> None:
        button = event.currentTarget
        if button.disabled:
            return
        button.disabled = True
        button.setAttribute("aria-busy", "true")
        button.textContent = "実行中"
        document.getElementById(prefix + "-audit").hidden = True
        document.getElementById(prefix + "-replay").hidden = True
        document.getElementById(prefix + "-copied").textContent = ""
        out = document.getElementById(prefix + "-response")
        out.textContent = "呼び出し中…"
        asyncio.ensure_future(send(button, out))

    async def copy_and_report() -> None:
        try:
            await window.navigator.clipboard.writeText(
                document.getElementById(prefix + "-curl").textContent
            )
            document.getElementById(prefix + "-copied").textContent = "コピーしました"
        except Exception:
            document.getElementById(
                prefix + "-copied"
            ).textContent = "コマンドを選択してコピーしてください"

    def audit_lookup(event: Any) -> None:
        action(trace_lookup, str(event.currentTarget.dataset.trace))(event)

    t.button(submit_label, type="button", classes="btn btn-primary", on_click=submit)
    t.pre("", id=prefix + "-response", classes="code", aria_live="polite")
    with t.section(id=prefix + "-replay", hidden=True):
        t.h4("今回のcurlコマンド")
        t.p("シェル変数 ACCESS_TOKEN に、この認証情報の有効なアクセストークンを設定してください。")
        t.pre("", id=prefix + "-curl", classes="code")
        t.button(
            "コマンドをコピー",
            type="button",
            classes="btn",
            on_click=lambda event: asyncio.ensure_future(copy_and_report()),
        )
        t.span("", role="status", id=prefix + "-copied")
    t.button(
        "この実行の業務操作履歴",
        type="button",
        classes="btn",
        hidden=True,
        id=prefix + "-audit",
        on_click=audit_lookup,
    )


def operation_definition(
    spec: dict[str, Any], operation: dict[str, Any], params: list[dict[str, Any]], body: dict[str, Any]
) -> None:
    """操作のパラメーターと応答仕様を表示する。"""
    if operation.get("description"):
        t.p(operation["description"])
    if params:
        t.h3("パラメータ")
    for p in params:
        required = "必須" if p["in"] == "path" or p.get("required") else "任意"
        t.p(
            f"{p['name']}（{p['in']} / {type_name(spec, p.get('schema', {}))} / {required}） {p.get('description', '')}"
        )
    if body:
        t.h3("リクエスト本文")
        if body.get("description"):
            t.p(body["description"])
        media_docs(spec, body.get("content", {}))
    t.h3("レスポンス")
    for code, raw_response in operation.get("responses", {}).items():
        if code.startswith("x-"):
            continue
        response = resolve(spec, raw_response)
        t.p(f"{code}　{response.get('description', '')}")
        media_docs(spec, response.get("content", {}))


def view(
    asset: dict[str, Any],
    rights: list[dict[str, Any]],
    keys: list[dict[str, Any]],
    *,
    subject: str,
    personal_project: str,
) -> None:
    """操作定義と実行欄を並べて表示する。"""
    spec = asset["spec"]
    rights = approved_rights(asset, rights, subject)
    bindings = available_bindings(asset["id"], rights, keys, subject)
    trial = trial_bindings(rights, personal_project) if not bindings else []
    issue_key = trial_key_issuer(asset) if trial else None
    with t.section(classes="box api-docs"):
        t.h2("API Docs")
        info = spec.get("info", {})
        t.p(
            f"{info.get('title', asset['name'])} · {info.get('version', '')} · OpenAPI {spec.get('openapi', '')}"
        )
        if info.get("description"):
            t.p(info["description"])
        t.h3("API操作一覧")
        index = 0
        for path, raw in spec["paths"].items():
            item = resolve(spec, raw)
            if not isinstance(item, dict):
                continue
            for method in METHODS:
                if method not in item:
                    continue
                name = method.upper() + " " + path
                allowed = asset.get("allowed_operations")
                if allowed is not None and name not in allowed:
                    continue
                usable = [
                    entry
                    for entry in bindings
                    if asset["id"] not in entry[0].get("operations", {})
                    or name in entry[0]["operations"][asset["id"]]
                ]
                if bindings and not usable:
                    continue
                operation = item[method]
                params = parameters(spec, item, operation)
                body = resolve(spec, operation.get("requestBody", {}))
                with t.details(classes="doc-operation", open=index == 0):
                    summary = operation.get("summary") or operation.get("operationId", "")
                    t.summary(f"{name}　{summary}".rstrip())
                    with t.div(classes="operation-columns"):
                        with t.div(classes="operation-definition"):
                            operation_definition(spec, operation, params, body)
                        with t.section(classes="operation-console"):
                            t.h3("この操作を呼び出す")
                            if method not in INVOKABLE:
                                t.p("このメソッドはポータルから実行できません。")
                            elif asset.get("suspended"):
                                t.p("このAPIは一時停止中です。")
                            elif usable:
                                try_operation(
                                    spec, asset, usable, method, path, params, body, f"docs-{index}"
                                )
                            elif trial:
                                t.p("初回の実行時に、このAPI専用の個人認証情報を発行します。")
                                try_operation(
                                    spec,
                                    asset,
                                    trial,
                                    method,
                                    path,
                                    params,
                                    body,
                                    f"docs-{index}",
                                    binding_label="プロジェクトと利用環境（必須）",
                                    submit_label="短期認証で呼び出す",
                                    issue_key=issue_key,
                                )
                            else:
                                t.p("呼び出しには利用申請の承認が必要です。")
                                t.a("申請の状況を確認する", href="#/mine")
                index += 1
        if not index:
            t.p("この利用者と認証情報で許可されている操作はありません。")
        if spec.get("components", {}).get("schemas"):
            with t.details():
                t.summary("データモデル")
                for name, raw in spec["components"]["schemas"].items():
                    t.h3(name)
                    t.pre(json.dumps(resolve(spec, raw), ensure_ascii=False, indent=2), classes="code")
