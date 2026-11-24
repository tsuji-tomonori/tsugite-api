# ロール・環境・操作の日本語表示名を定義する。
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
    "profile.invite_set": "招待時のプロフィール登録",
    "profile.self_update": "本人によるプロフィール変更",
    "profile.admin_update": "管理者によるプロフィール変更",
    "notify": "通知送信",
    "alert.configure": "ルール変更",
    "alert.trigger": "しきい値到達",
    "invoke.start": "呼び出し開始",
    "invoke.end": "応答",
    "invoke.denied": "呼び出し拒否",
    "invoke.error": "呼び出しエラー",
}


ROLE_LABELS = {"provider": "提供者", "consumer": "利用者", "admin": "管理者", "auditor": "監査担当"}
