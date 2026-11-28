# ポータルのログインフォームを描画する。
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote, urlencode

import segno
from apis import client
from apis.portal_auth import PortalLogin
from js import document, window
from puepy import t

STEPS = {
    "signin": ("継手APIにログイン", "社内アカウントでAPIポータルにログインしてください。", "ログイン"),
    "new_password": (
        "初回パスワードの変更",
        "次回から使用するパスワードを設定してください。",
        "パスワードを設定",
    ),
    "setup": (
        "認証アプリの登録",
        "認証アプリでQRコードを読み取り、アプリに表示される6桁の確認コードを入力してください。",
        "登録してログイン",
    ),
    "mfa": ("本人確認", "認証アプリに表示された6桁のコードを入力してください。", "確認してログイン"),
    "finish_setup": (
        "登録の完了",
        "認証アプリの確認が済みました。ログインを完了してください。",
        "ログインを完了",
    ),
    "forgot": (
        "パスワードの再設定",
        "ユーザー名を入力すると、登録した連絡先に確認コードが届きます。",
        "確認コードを送信",
    ),
    "confirm_reset": (
        "新しいパスワードの設定",
        "届いた確認コードと、新しいパスワードを入力してください。",
        "パスワードを再設定",
    ),
}


def auth_input(label: str, name: str, **attrs: Any) -> None:
    """認証用の入力欄を作る。"""
    with t.label(classes="field"):
        t.span(label)
        t.input(id=name, name=name, classes="form-control", required=True, **attrs)


def registration_codes(username: str, secret: str) -> None:
    """認証アプリ用のQRコードと、手動登録用の設定コードを表示する。"""
    issuer = "継手API"
    label = quote(issuer, safe="") + ":" + quote(username.replace(":", "："), safe="")
    query = urlencode({"secret": secret, "issuer": issuer})
    qr = segno.make_qr(f"otpauth://totp/{label}?{query}")
    t.img(
        src=qr.png_data_uri(scale=5, border=4, dark="black", light="white"),
        alt="認証アプリ登録用のQRコード",
        classes="auth-qr",
    )

    async def copy_code() -> None:
        status = document.getElementById("auth-copy-status")
        try:
            await window.navigator.clipboard.writeText(secret)
            status.textContent = "設定コードをコピーしました。"
        except Exception:
            status.textContent = "設定コードを選択してコピーしてください。"

    with t.details(classes="auth-manual"):
        t.summary("設定コードを表示")
        t.p("認証アプリで時間ベースの登録を選び、次の設定コードを入力してください。")
        t.code(secret, classes="auth-key")
        t.button(
            "設定コードをコピー",
            type="button",
            classes="btn",
            on_click=lambda event: asyncio.ensure_future(copy_code()),
        )
        t.span("", id="auth-copy-status", role="status")


def portal_form(
    ctx: dict[str, Any],
    action: Callable[..., Callable[[Any], None]],
    store: Any,
    refresh: Callable[[], Awaitable[None]],
) -> None:
    """現在の認証手順に合うフォームを表示する。"""
    if "login_flow" not in ctx:
        ctx["login_flow"] = PortalLogin(ctx["config"])
    flow = ctx["login_flow"]
    step = flow.step
    title, subtitle, submit_label = STEPS[step]

    async def switch(next_step: str) -> None:
        user = document.getElementById("login-user")
        if user:
            flow.username = str(user.value).strip()
        flow.reset(next_step)

    async def submit() -> None:
        def read(name: str) -> str:
            node = document.getElementById(name)
            return str(node.value) if node else ""

        password = read("login-password")
        if step in {"new_password", "confirm_reset"} and password != read("login-repeat"):
            raise client.InputError("新しいパスワードと確認用の入力が一致しません。")
        token = await flow.submit(
            username=read("login-user"), password=password, code=read("login-code")
        )
        if token:
            del ctx["login_flow"]
            store.setItem("access", token)
            store.setItem("portal_login", "1")
            await refresh()
        elif step == "confirm_reset":
            ctx["message"] = "パスワードを再設定しました。新しいパスワードでログインしてください。"

    t.h1(title)
    t.p(subtitle, classes="auth-intro")
    with t.form(classes="auth-form", on_submit=action(submit)):
        if step in {"signin", "forgot"}:
            auth_input(
                "ユーザー名", "login-user", type="text", value=flow.username, autocomplete="username"
            )
        if step == "setup":
            registration_codes(flow.username, flow.secret)
        if step in {"mfa", "setup", "confirm_reset"}:
            auth_input(
                "確認コード",
                "login-code",
                type="text",
                inputmode="numeric",
                pattern="[0-9]{6}",
                maxlength=6,
                autocomplete="one-time-code",
            )
        if step == "signin":
            auth_input("パスワード", "login-password", type="password", autocomplete="current-password")
        if step in {"new_password", "confirm_reset"}:
            t.p(
                "14文字以上で、英大文字・英小文字・数字・記号をそれぞれ含めてください。",
                id="password-rules",
            )
            auth_input(
                "新しいパスワード",
                "login-password",
                type="password",
                minlength=14,
                autocomplete="new-password",
                aria_describedby="password-rules",
            )
            auth_input(
                "新しいパスワード（確認）", "login-repeat", type="password", autocomplete="new-password"
            )
        t.button(submit_label, type="submit", classes="btn btn-primary")
    label, target = (
        ("パスワードを忘れた方", "forgot") if step == "signin" else ("ログインに戻る", "signin")
    )
    t.button(label, type="button", classes="auth-link", on_click=action(switch, target))
