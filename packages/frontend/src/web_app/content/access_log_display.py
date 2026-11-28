"""アクセスログの一件を表示用に整える。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

LOG_QUESTIONS = ("結果とエラーを教えて", "処理に何ミリ秒かかった？", "誰がどのAPIを呼び出した？")


def timestamp(value: str) -> str:
    """時刻をミリ秒単位のUTC表記にする。"""
    stamp = datetime.fromisoformat(value).astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%d %H:%M:%S.") + f"{stamp.microsecond // 1000:03} UTC"


def result_label(status: int) -> str:
    """HTTPステータスの結果区分を返す。"""
    return ("情報", "成功", "リダイレクト", "クライアントエラー", "サーバーエラー")[status // 100 - 1]


def timing(row: dict[str, Any]) -> tuple[str, str]:
    """記録した時刻または推定時刻を求める。"""
    if row["started_at"] and row["responded_at"]:
        return timestamp(row["started_at"]), timestamp(row["responded_at"])
    recorded = datetime.fromisoformat(row["at"])
    return (
        timestamp((recorded - timedelta(milliseconds=row["duration_ms"])).isoformat()) + "（推定）",
        timestamp(row["at"]) + "（記録時刻から推定）",
    )


def detail_fields(row: dict[str, Any]) -> list[tuple[str, str]]:
    """詳細表の項目名と値を組み立てる。"""
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


def answer_log_question(row: dict[str, Any], question: str) -> str | None:
    """一件の記録から答えられる質問に回答する。"""
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
    if not labels and text.strip(" ？?。") not in (
        "概要",
        "詳細",
        "まとめ",
        "概要を教えて",
        "詳細を教えて",
        "この呼び出しの概要を教えて",
    ):
        return None
    fields = detail_fields(row)
    return "\n".join(f"{label}　{value}" for label, value in fields if not labels or label in labels)
