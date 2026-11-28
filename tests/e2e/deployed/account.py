"""実環境テスト専用の利用者と接続先を照合し、認証アプリと同じ時刻ベースの本人確認コードを生成する。"""

import base64
import hashlib
import hmac
import re


def portal_origin(url: str) -> str:
    if not re.fullmatch(r"https://[a-z0-9]+\.cloudfront\.net/?", url):
        raise ValueError("E2E_PORTAL_URL にスタック出力 PortalUrl を指定してください")
    return url.rstrip("/")


def totp(seed: str, timestamp: int) -> str:
    encoded = seed.strip().upper()
    key = base64.b32decode(encoded + "=" * (-len(encoded) % 8))
    counter = (timestamp // 30).to_bytes(8, "big")
    digest = hmac.digest(key, counter, hashlib.sha1)
    offset = digest[-1] & 15
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def is_test_consumer(profile: dict[str, object], subject: str) -> bool:
    return (
        bool(subject)
        and profile.get("subject") == subject
        and profile.get("admin") is False
        and profile.get("auditor") is False
        and isinstance(profile.get("projects"), list)
        and profile.get("owners") == profile["projects"]
        and profile.get("leads") == []
    )
