"""ログイン方法に応じた操作欄を描画する。"""

from __future__ import annotations

from apis import client
from puepy import t
from runtime.portal_session import login, login_member, refresh_session
from runtime.portal_ui import action, ctx

from components import login_views
from components.controls import btn, field


def login_panel() -> None:
    """設定に応じてデモまたは認証フォームを表示する。"""
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
