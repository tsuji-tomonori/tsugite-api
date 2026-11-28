"""複数画面で使うボタンと入力欄を描画する。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from puepy import t
from puepy.core import Tag
from runtime.portal_ui import action


def btn(label: str, fn: Callable[..., Awaitable[None]] | None, *args: Any, primary: bool = False) -> Tag:
    """クリックで非同期処理を実行するボタンを作る。"""
    return t.button(
        label,
        type="button",
        classes="btn btn-primary" if primary else "btn btn-outline-secondary",
        **({"on_click": action(fn, *args)} if fn is not None else {}),
    )


def field(
    label: str,
    name: str,
    options: Sequence[tuple[str, str]] | None = None,
    textarea: bool = False,
    text: str = "",
    placeholder: str = "",
    required: bool | None = None,
) -> None:
    """ラベルと必須表示を持つ入力欄を作る。"""
    with t.label(classes="field"):
        if required is not None:
            label += "（必須）" if required else "（任意）"
        t.span(label, id=name + "-label")
        if options is not None:
            with t.select(
                id=name, required=bool(required), aria_labelledby=name + "-label", classes="form-select"
            ):
                for key, title in options:
                    t.option(title, value=key, selected=(key == text))
        elif textarea:
            t.textarea(
                text, id=name, classes="form-control", required=bool(required), placeholder=placeholder
            )
        else:
            t.input(
                id=name,
                value=text,
                classes="form-control",
                required=bool(required),
                placeholder=placeholder,
            )
