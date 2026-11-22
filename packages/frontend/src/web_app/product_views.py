"""Product publication, release history and environment-specific application forms."""

import client
from js import document
from puepy import t

ENV = {"sandbox": "基本版（検証）", "staging": "準本番", "production": "本番"}
ROUTES = {
    "provider": "提供者が承認",
    "department_provider": "所属部署が承認 → 提供者が承認",
    "department": "所属部署が承認",
    "auto": "申請条件を満たせば自動承認",
    "custom": "承認者と順番を指定",
    "legacy": "商品共通の承認ルールを使用",
}


def field_row(spec):
    with t.div(classes="application-field"):
        with t.label(classes="field"):
            t.span("申請項目名")
            t.input(
                classes="form-control field-name",
                value=spec.get("label", ""),
                placeholder="テスト実施ID",
            )
        with t.label(classes="scope-choice"):
            t.input(type="checkbox", classes="field-required", checked=spec.get("required", True))
            t.span("入力必須")
        with t.label(classes="field"):
            t.span("受理する値（任意・1行に1件）")
            t.textarea("\n".join(spec.get("allowed_values", [])), classes="form-control field-values")
        t.button("項目を削除", type="button", classes="btn", data_remove="yes")


def step_label(step):
    return {"provider": "提供者", "department": "申請者の所属部署"}.get(step, step.removeprefix("unit/"))


def step_row(step, units):
    with t.div(classes="approval-step"):
        with t.label(classes="field"):
            t.span("承認先")
            with t.select(classes="form-select"):
                for key, title in [("provider", "提供者"), ("department", "申請者の所属部署")] + [
                    ("unit/" + u["id"], u["name"]) for u in units if u["kind"] == "department"
                ]:
                    t.option(title, value=key, selected=key == step)
        t.button("段階を削除", type="button", classes="btn", data_remove="step")


def offer_editor(env, rule, field, existing, units):
    prefix = "offer-" + env
    with t.details(classes="offer-editor"):
        t.summary(ENV[env] + "の利用・承認条件")
        field("利用の説明", prefix + "-instructions", textarea=True, text=rule.get("instructions", ""))
        field("同意を必須にする利用規約", prefix + "-terms", textarea=True, text=rule.get("terms", ""))
        field(
            "承認フロー",
            prefix + "-route",
            options=list(ROUTES.items()),
            text=rule.get("route", "legacy" if existing or env != "production" else "provider"),
        )

        def manage(event):
            target = event.target
            if target.getAttribute("data-add") == "step":
                template = document.getElementById(prefix + "-step-template").firstElementChild
                document.getElementById(prefix + "-steps").appendChild(template.cloneNode(True))
            elif target.getAttribute("data-remove") == "step":
                target.closest(".approval-step").remove()
            elif target.getAttribute("data-remove") == "yes":
                target.closest(".application-field").remove()
            elif target.getAttribute("data-add") == "yes":
                template = document.getElementById(prefix + "-template").firstElementChild
                document.getElementById(prefix + "-fields").appendChild(template.cloneNode(True))

        with t.div(on_click=manage):
            with t.details(open=rule.get("route") == "custom"):
                t.summary("カスタム承認の順番")
                t.p("「承認者と順番を指定」を選び、承認先を順に追加してください。")
                with t.div(id=prefix + "-steps"):
                    for step in rule.get("steps", []):
                        step_row(step, units)
                with t.div(id=prefix + "-step-template", hidden=True):
                    step_row("provider", units)
                t.button("承認段階を追加", type="button", classes="btn", data_add="step")
            with t.div(id=prefix + "-fields"):
                for spec in rule.get("fields", []):
                    field_row(spec)
            with t.div(id=prefix + "-template", hidden=True):
                field_row({})
            t.button("申請項目を追加", type="button", classes="btn", data_add="yes")


def read_offer(env, value):
    prefix = "offer-" + env
    fields = []
    rows = document.getElementById(prefix + "-fields").children
    for i in range(rows.length):
        row = rows.item(i)
        label = str(row.querySelector(".field-name").value).strip()
        if not label:
            raise client.InputError(ENV[env] + "の申請項目名を入力してください")
        fields.append(
            {
                "label": label,
                "required": bool(row.querySelector(".field-required").checked),
                "allowed_values": [
                    v.strip()
                    for v in str(row.querySelector(".field-values").value).splitlines()
                    if v.strip()
                ],
            }
        )
    steps = document.getElementById(prefix + "-steps").querySelectorAll("select")
    return {
        "steps": [str(steps.item(i).value) for i in range(steps.length)]
        if value(prefix + "-route") == "custom"
        else [],
        "instructions": value(prefix + "-instructions"),
        "terms": value(prefix + "-terms"),
        "route": value(prefix + "-route"),
        "fields": fields,
    }


def requirements(asset, env, field, first):
    rule = asset.get("offers", {}).get(env, {})
    with t.div(id="requirements-" + env, hidden=not first):
        t.p("承認フロー　" + ROUTES[rule.get("route", "legacy")])
        if rule.get("steps"):
            t.p(" → ".join(step_label(s) for s in rule["steps"]))
        if rule.get("instructions"):
            t.p(rule["instructions"], classes="terms-text")
        if rule.get("terms"):
            t.h3("利用規約")
            t.p(rule["terms"], classes="terms-text")
            with t.label(classes="scope-choice"):
                t.input(id="agree-" + env, type="checkbox")
                t.span(ENV[env] + "の利用規約に同意する")
        for i, item in enumerate(rule.get("fields", [])):
            field(item["label"] + ("（必須）" if item["required"] else "（任意）"), f"answer-{env}-{i}")


def application_form(asset, field):
    envs = asset["environments"]

    def select_env(event):
        selected = str(event.target.value)
        for env in envs:
            document.getElementById("requirements-" + env).hidden = env != selected

    with t.label(classes="field"):
        t.span("環境")
        with t.select(id="environment", classes="form-select", on_change=select_env):
            for env in envs:
                t.option(ENV[env], value=env)
    for i, env in enumerate(envs):
        requirements(asset, env, field, i == 0)


def answers(asset, env, value):
    rule = asset.get("offers", {}).get(env, {})
    data = {}
    for i, item in enumerate(rule.get("fields", [])):
        answer = value(f"answer-{env}-{i}")
        if item["required"] and not answer:
            raise client.InputError(item["label"] + "を入力してください")
        if answer:
            data[item["label"]] = answer
    accepted = bool(rule.get("terms") and document.getElementById("agree-" + env).checked)
    if rule.get("terms") and not accepted:
        raise client.InputError("利用規約への同意が必要です")
    return {"answers": data, "terms_accepted": accepted, "offer_version": rule.get("version", "")}


def release_history(asset):
    if not asset.get("releases"):
        return
    with t.details(classes="box"):
        t.summary("公開版の変更履歴")
        for row in asset["releases"]:
            t.h3(f"第{row['number']}版 · API {row['api_version']} · OpenAPI {row['openapi']}")
            t.small(row["published_at"][:10])
            if row["note"]:
                t.p(row["note"], classes="terms-text")
            for key, title in (("added", "追加"), ("changed", "変更"), ("removed", "削除")):
                if row[key]:
                    t.p(title + "　" + "、".join(row[key]))
