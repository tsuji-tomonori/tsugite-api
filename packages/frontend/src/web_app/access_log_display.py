"""アクセスログの表示と、その1件を根拠とする質問への回答。"""

from datetime import datetime, timedelta, timezone

LOG_QUESTIONS = ("結果とエラーを教えて", "処理に何ミリ秒かかった？", "誰がどのAPIを呼び出した？")


def timestamp(value):
    stamp = datetime.fromisoformat(value).astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%d %H:%M:%S.") + f"{stamp.microsecond // 1000:03} UTC"


def result_label(status):
    return ("情報", "成功", "リダイレクト", "クライアントエラー", "サーバーエラー")[status // 100 - 1]


def timing(row):
    if row["started_at"] and row["responded_at"]:
        return timestamp(row["started_at"]), timestamp(row["responded_at"])
    recorded = datetime.fromisoformat(row["at"])
    return (
        timestamp((recorded - timedelta(milliseconds=row["duration_ms"])).isoformat()) + "（推定）",
        timestamp(row["at"]) + "（記録時刻から推定）",
    )


def detail_fields(row):
    start, end = timing(row)
    fields = [
        ("リクエストID", row["request_id"]),
        ("呼び出し開始", start),
        ("応答", end),
        ("処理時間", f"{row['duration_ms']} ms"),
        ("結果", f"{result_label(row['status'])}（HTTP {row['status']}）"),
    ]
    if row["status"] >= 400:
        fields.append(("エラーコード", row["error_code"] or f"http_{row['status']}"))
    return fields + [
        ("HTTPメソッド", row["method"]),
        ("操作パス", row["operation"] or "未記録"),
        ("API ID", row["asset_id"]),
        ("呼び出し元ID", row["actor"]),
        ("キーID", row["key_id"] or "なし"),
        ("提供元ID", row["owner"]),
        ("利用プロジェクトID", row["project"] or "未記録"),
        ("環境", row["environment"]),
    ]


def answer_log_question(row, question):
    text = question.casefold()
    topics = (
        (
            ("いつ", "時刻", "時間", "開始", "応答", "秒", "遅", "かかっ"),
            ("呼び出し開始", "応答", "処理時間"),
        ),
        (
            ("結果", "成功", "失敗", "エラー", "なぜ", "原因", "ステータス", "拒否", "コード", "http"),
            ("結果", "エラーコード"),
        ),
        (("誰", "だれ", "利用者", "呼び出し元"), ("呼び出し元ID",)),
        (("api", "操作", "パス", "メソッド"), ("API ID", "HTTPメソッド", "操作パス")),
        (("キー", "認証"), ("キーID",)),
        (("提供", "プロジェクト", "環境"), ("提供元ID", "利用プロジェクトID", "環境")),
        (
            ("識別", "id"),
            ("リクエストID", "API ID", "呼び出し元ID", "キーID", "提供元ID", "利用プロジェクトID"),
        ),
    )
    labels = {label for words, group in topics if any(word in text for word in words) for label in group}
    fields = detail_fields(row)
    if not labels and not any(word in text for word in ("概要", "詳細", "まとめ", "何が", "教えて")):
        return "この記録からは判断できません。開始・応答時刻、処理時間、結果、識別子について質問できます。詳しい調査は運営に問い合わせてください。"
    return "\n".join(f"{label}　{value}" for label, value in fields if not labels or label in labels)
