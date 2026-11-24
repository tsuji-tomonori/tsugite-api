# DOMイベントの登録境界を宣言する。
from collections.abc import Callable
from typing import Any

def add_event_listener(target: Any, event: str, listener: Callable[[Any], None]) -> None: ...
