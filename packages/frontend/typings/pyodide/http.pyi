# ブラウザー内蔵のHTTPクライアントを宣言する。
from typing import Any

async def pyfetch(url: str, **options: Any) -> Any: ...
