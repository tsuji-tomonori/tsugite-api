"""商品の利用条件と公開履歴を表示する。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apis import client
from js import document
from puepy import t
from runtime.portal_ui import ctx

ENV = {"sandbox": "基本版（検証）", "staging": "準本番", "production": "本番"}
ROUTES = {
    "provider": "提供者が承認",
    "department_provider": "所属部署が承認 → 提供者が承認",
    "department": "所属部署が承認",
    "auto": "申請条件を満たせば自動承認",
    "custom": "承認者と順番を指定",
    "legacy": "商品共通の承認ルールを使用",
}


def field_row(spec: dict[str, Any]) -> None:
    """利用申請項目の編集行を表示する。"""
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


def step_label(step: str) -> str:
    """承認ステップの表示名を返す。"""
    return dict(approval_options()).get(step, step)


def approval_options() -> list[tuple[str, str]]:
    """指定可能な組織と利用者を名前付きの選択肢にする。"""
    directory = ctx.get("policy_directory", {})
    return [
        ("admin", "管理者"),
        ("project_leader", "提供プロジェクトのリーダー"),
        ("provider", "提供プロジェクトのメンバー"),
        ("department", "申請者の所属部署の上長"),
        *[
            ("unit/" + u["id"], u["name"] + "のリーダー")
            for u in directory.get("units", [])
            if u["kind"] in ("project", "department")
        ],
        *[
            (
                "person/" + u["subject"],
                (u.get("full_name") or u["username"]) + "（" + u["username"] + "）",
            )
            for u in directory.get("users", [])
        ],
    ]


def step_row(step: str, units: list[dict[str, Any]]) -> None:
    """承認ステップの編集行を表示する。"""
    with t.div(classes="approval-step"):
        with t.label(classes="field"):
            t.span("承認先")
            with t.select(classes="form-select"):
                choices = dict(approval_options())
                choices.update(
                    {
                        ("unit/" + u["id"]): u["name"] + "のリーダー"
                        for u in units
                        if u["kind"] in ("project", "department")
                    }
                )
                if step:
                    choices.setdefault(step, step)
                for key, title in choices.items():
                    t.option(title, value=key, selected=key == step)
                t.option("ユーザー名で指名", value="person/")
                t.option("組織IDでリーダーを指定", value="unit/")
        with t.label(classes="field step-identifier"):
            t.span("承認先のユーザー名または組織ID")
            t.input(classes="form-control", type="text")
        t.button("段階を削除", type="button", classes="btn", data_remove="step")


def selected_step(element: Any) -> str:
    """選択した承認先または入力した個別の宛先を読み取る。"""
    key = str(element.value)
    if key in ("person/", "unit/"):
        identifier = str(element.closest(".approval-step").querySelector("input").value).strip()
        if not identifier:
            raise client.InputError("承認先のユーザー名または組織IDを入力してください")
        return key + identifier
    return key


def offer_editor(
    env: str,
    rule: dict[str, Any],
    field: Callable[..., None],
    existing: bool,
    units: list[dict[str, Any]],
) -> None:
    """環境別の利用条件編集欄を描画する。"""
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

        def manage(event: Any) -> None:
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


def read_offer(env: str, value: Callable[[str], str]) -> dict[str, Any]:
    """編集欄から利用条件を読み取る。"""
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
        "steps": [selected_step(steps.item(i)) for i in range(steps.length)]
        if value(prefix + "-route") == "custom"
        else [],
        "instructions": value(prefix + "-instructions"),
        "terms": value(prefix + "-terms"),
        "route": value(prefix + "-route"),
        "fields": fields,
    }


def requirements(asset: dict[str, Any], env: str, field: Callable[..., None], first: bool) -> None:
    """環境別の利用条件と規約を表示する。"""
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
                t.input(id="agree-" + env, type="checkbox", required=True)
                t.span(ENV[env] + "の利用規約に同意する（必須）")
        for i, item in enumerate(rule.get("fields", [])):
            field(item["label"], f"answer-{env}-{i}", required=item["required"])


def application_form(asset: dict[str, Any], field: Callable[..., None]) -> None:
    """利用申請の入力欄を組み立てる。"""
    envs = asset["environments"]

    def select_env(event: Any) -> None:
        selected = str(event.target.value)
        for env in envs:
            document.getElementById("requirements-" + env).hidden = env != selected

    with t.label(classes="field"):
        t.span("環境（必須）")
        with t.select(id="environment", classes="form-select", required=True, on_change=select_env):
            for env in envs:
                t.option(ENV[env], value=env)
    for i, env in enumerate(envs):
        requirements(asset, env, field, i == 0)


def answers(asset: dict[str, Any], env: str, value: Callable[[str], str]) -> dict[str, Any]:
    """入力された回答・規約同意・版を読み取る。"""
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


def release_history(asset: dict[str, Any]) -> None:
    """公開版ごとの変更内容を表で表示する。"""
    if not asset.get("releases"):
        return
    with t.details(classes="box release-history"):
        with t.summary():
            t.span("公開版の変更履歴", id="release-history-heading")
        with (
            t.div(
                classes="table-scroll release-table",
                role="region",
                aria_labelledby="release-history-heading",
                tabindex="0",
            ),
            t.table(aria_labelledby="release-history-heading"),
        ):
            with t.thead(), t.tr():
                for label in (
                    "公開版",
                    "公開日",
                    "APIバージョン",
                    "OpenAPI",
                    "変更内容",
                    "提供者の説明",
                ):
                    t.th(label, scope="col")
            with t.tbody():
                for row in asset["releases"]:
                    with t.tr():
                        t.th(f"第{row['number']}版", scope="row")
                        published = row["published_at"][:10]
                        with t.td():
                            t.time(published, datetime=published)
                        t.td(row["api_version"])
                        t.td(row["openapi"])
                        changes = [
                            (title, row[key])
                            for key, title in (
                                ("added", "追加"),
                                ("changed", "変更"),
                                ("removed", "削除"),
                            )
                            if row[key]
                        ]
                        with t.td():
                            if changes:
                                with t.dl():
                                    for title, items in changes:
                                        t.dt(title)
                                        with t.dd(), t.ul():
                                            for item in items:
                                                t.li(item)
                            else:
                                t.span("—")
                        t.td(row["note"] or "—", classes="terms-text")
