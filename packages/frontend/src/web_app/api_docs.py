"""Local OpenAPI documentation and authenticated, same-origin operation console."""

import asyncio
import json
from urllib.parse import quote, unquote, urlencode

import client
from js import document
from openapi_fields import parameters, resolve
from puepy import t
from pyodide.http import pyfetch

METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
INVOKABLE = frozenset(("get", "post", "put", "patch", "delete"))
ENVIRONMENTS = {"sandbox": "検証", "production": "本番"}


def type_name(spec, schema):
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


def data_schema(spec, media):
    schema = media.get("schema")
    if schema is not None:
        t.pre(json.dumps(resolve(spec, schema), ensure_ascii=False, indent=2), classes="code")


def media_docs(spec, content):
    for media_type, media in content.items():
        if not isinstance(media, dict):
            continue
        with t.details():
            t.summary(media_type + " のスキーマ")
            data_schema(spec, media)


def available_bindings(asset_id, rights, keys, subject):
    options = []
    seen = set()
    for key in keys:
        if key.get("revoked") or key.get("revoked_at"):
            continue
        if key.get("api_ids") and asset_id not in key["api_ids"]:
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
            options.append((key["id"], env, key["project"], label))
    return options


def value(element_id):
    return str(document.getElementById(element_id).value)


def param_values(spec, param, value_text):
    schema = resolve(spec, param.get("schema", {}))
    kind = schema.get("type") if isinstance(schema, dict) else ""
    if kind in ("array", "object"):
        try:
            data = json.loads(value_text)
        except ValueError as exc:
            raise ValueError(f"{param['name']} はJSONで指定してください") from exc
        if not isinstance(data, list if kind == "array" else dict):
            raise ValueError(f"{param['name']} の型は {kind} です")
        return data
    return value_text


def stringify(value):
    return (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )


def build_location(spec, path, params, entered):
    decoded_path = unquote(path)
    if (
        not path.startswith("/")
        or any(c in decoded_path for c in ("?", "#", "\\"))
        or any(p in (".", "..") for p in decoded_path.split("/"))
        or any(ord(c) < 32 for c in decoded_path)
    ):
        raise ValueError("この操作パスをポータルから呼び出すことはできません")
    query = []
    for i, param in enumerate(params):
        where, name = param["in"], param["name"]
        if where not in ("path", "query"):
            continue
        text = entered.get(i, "")
        if text == "":
            if where == "path" or param.get("required"):
                raise ValueError(f"{name} を入力してください")
            continue
        data = param_values(spec, param, text)
        style = param.get("style", "form" if where == "query" else "simple")
        explode = param.get("explode", style == "form")
        seq = [stringify(v) for v in data] if isinstance(data, list) else []
        pairs = [(k, stringify(v)) for k, v in data.items()] if isinstance(data, dict) else []
        if where == "path":
            if style != "simple":
                raise ValueError("この操作の実行には simple 形式のパスパラメータが必要です")
            if isinstance(data, list):
                encoded = ",".join(quote(v, safe="") for v in seq)
            elif isinstance(data, dict):
                sep = "=" if explode else ","
                encoded = ",".join(quote(k, safe="") + sep + quote(v, safe="") for k, v in pairs)
            else:
                encoded = quote(stringify(data), safe="")
            if encoded in (".", ".."):
                raise ValueError(f"{name} の値を確認してください")
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
        raise ValueError("必要なパスパラメータが仕様に定義されていません")
    return path + ("?" + urlencode(query) if query else "")


def option_list(label, element_id, choices):
    with t.label(classes="field"):
        t.span(label)
        with t.select(id=element_id, classes="form-select", aria_label=label):
            for key, text in choices:
                t.option(text, value=key)


def input_param(spec, param, element_id):
    schema = resolve(spec, param.get("schema", {}))
    sample = param.get("example")
    if sample is None and isinstance(schema, dict):
        sample = schema.get("example", schema.get("default"))
    with t.label(classes="field"):
        t.span(param["name"] + "（" + param["in"] + "）")
        t.input(
            id=element_id,
            classes="form-control",
            placeholder=stringify(sample) if sample is not None else type_name(spec, schema),
        )


def try_operation(spec, asset, bindings, method, path, params, body, prefix):
    option_list(
        "利用するAPIキーと環境",
        prefix + "-key",
        [(str(i), b[3]) for i, b in enumerate(bindings)],
    )
    for i, param in enumerate(params):
        if param["in"] in ("query", "path"):
            input_param(spec, param, prefix + f"-param-{i}")
    content = body.get("content", {})
    if content:
        option_list("本文の形式", prefix + "-media", [(k, k) for k in content])
        with t.label(classes="field"):
            t.span("送信するリクエスト本文")
            t.textarea(id=prefix + "-body", classes="form-control")

    async def send(button, out):
        try:
            kid, env, project, _ = bindings[int(value(prefix + "-key"))]
            entered = {
                i: value(prefix + f"-param-{i}")
                for i, p in enumerate(params)
                if p["in"] in ("query", "path")
            }
            location = build_location(spec, path, params, entered)
            headers = {
                "Authorization": "Bearer " + str(client.store.getItem("access")),
                "X-Tsugite-Key-Id": kid,
            }
            opts = {"method": method.upper(), "headers": headers}
            if content:
                text = value(prefix + "-body")
                if not text and body.get("required"):
                    raise ValueError("リクエスト本文を入力してください")
                if text:
                    media = value(prefix + "-media")
                    if media == "application/json" or media.endswith("+json"):
                        try:
                            json.loads(text)
                        except ValueError as exc:
                            raise ValueError("リクエスト本文は正しいJSONで入力してください") from exc
                    headers["Content-Type"] = media
                    opts["body"] = text
            segments = [quote(part, safe="") for part in (asset["id"], env, project)]
            result = await pyfetch(client.prefix + "/invoke/" + "/".join(segments) + location, **opts)
            trace = result.headers.get("x-request-id", "")
            response = await result.string()
            if len(response) > 12000:
                response = response[:12000] + "\n（先頭12,000文字まで表示）"
            out.textContent = f"HTTP {result.status}\nリクエストID　{trace}\n{response}"
        except Exception as exc:
            out.textContent = str(exc)
        finally:
            button.disabled = False

    def submit(event):
        button = event.currentTarget
        if button.disabled:
            return
        button.disabled = True
        out = document.getElementById(prefix + "-response")
        out.textContent = "呼び出し中…"
        asyncio.ensure_future(send(button, out))

    t.button("選んだキーで実行", type="button", classes="btn btn-primary", on_click=submit)
    t.pre("", id=prefix + "-response", classes="code", aria_live="polite")


def view(asset, rights, keys, *, subject=""):
    spec = asset["spec"]
    bindings = available_bindings(asset["id"], rights, keys, subject)
    with t.section(classes="box"):
        t.h2("API Docs")
        info = spec.get("info", {})
        t.p(
            f"{info.get('title', asset['name'])} · {info.get('version', '')} · OpenAPI {spec.get('openapi', '')}"
        )
        if info.get("description"):
            t.p(info["description"])
        index = 0
        for path, raw in spec["paths"].items():
            item = resolve(spec, raw)
            if not isinstance(item, dict):
                continue
            for method in METHODS:
                if method not in item:
                    continue
                operation = item[method]
                params = parameters(spec, item, operation)
                body = resolve(spec, operation.get("requestBody", {}))
                with t.details():
                    t.summary(
                        f"{method.upper()} {path}　{operation.get('summary') or operation.get('operationId', '')}"
                    )
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
                    if bindings and method in INVOKABLE:
                        t.h3("この操作を呼び出す")
                        try_operation(spec, asset, bindings, method, path, params, body, f"docs-{index}")
                    index += 1
        if spec.get("components", {}).get("schemas"):
            with t.details():
                t.summary("データモデル")
                for name, raw in spec["components"]["schemas"].items():
                    t.h3(name)
                    t.pre(json.dumps(resolve(spec, raw), ensure_ascii=False, indent=2), classes="code")
        if not bindings:
            t.p(
                "呼び出すには、承認済みの環境と、このAPIを利用できる有効なAPIキーが必要です。",
                classes="muted",
            )
            t.a("APIキーの作成・管理を開く", href="#/keys")
