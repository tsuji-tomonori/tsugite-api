"""PuePyの描画タグと子要素を追加するコンテキストを宣言する。"""

from types import TracebackType
from typing import Self

class Tag:
    def __enter__(self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None: ...

class Component(Tag):
    props: list[str]
    state: dict[str, str]
