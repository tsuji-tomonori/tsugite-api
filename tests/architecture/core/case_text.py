# テストケースの説明に使う書式。
"""テストケースの説明に使う書式。"""

import re

KANA = re.compile(r"[ぁ-ゖァ-ヺ]")


def is_japanese_case_text(text):
    return 8 <= len(text) <= 100 and len(text.splitlines()) == 1 and bool(KANA.search(text))
