"""ポータルと共通の表示モードを使うログインフォーム。"""

from js import document
from portal_auth import PortalLogin
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
        "認証アプリで設定キーを手入力し、時間ベースのアカウントを追加してください。",
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


def auth_input(label, name, **attrs):
    with t.label(classes="field"):
        t.span(label)
        t.input(id=name, name=name, classes="form-control", required=True, **attrs)


def portal_form(ctx, action, store, refresh):
    if "login_flow" not in ctx:
        ctx["login_flow"] = PortalLogin(ctx["config"])
    flow = ctx["login_flow"]
    step = flow.step
    title, subtitle, submit_label = STEPS[step]

    async def switch(next_step):
        user = document.getElementById("login-user")
        if user:
            flow.username = str(user.value).strip()
        flow.reset(next_step)

    async def submit():
        def read(name):
            node = document.getElementById(name)
            return str(node.value) if node else ""

        password = read("login-password")
        if step in {"new_password", "confirm_reset"} and password != read("login-repeat"):
            raise ValueError("新しいパスワードと確認用の入力が一致しません。")
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
            t.strong("設定キー")
            t.code(flow.secret, classes="auth-key")
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
