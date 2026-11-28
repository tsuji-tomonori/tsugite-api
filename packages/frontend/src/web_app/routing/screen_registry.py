"""画面ディレクトリからルートとメニューを組み立てる。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from functools import cache
from importlib import import_module
from pkgutil import iter_modules
from typing import Any

import pages


@dataclass(frozen=True)
class Screen:
    path: str
    title: str | Callable[[], str]
    view: Callable[[], None]
    load_data: Callable[[str], Awaitable[None]] | None = None
    group: str = ""
    order: int = 0
    visible: Callable[[dict[str, Any]], bool] = lambda user: True
    parent: str = ""
    description: str = ""
    heading_action: Callable[[], object] | None = None
    own_heading: bool = False
    clear_on_load: tuple[str, ...] = ()

    menu_paths: Callable[[dict[str, Any]], list[tuple[str, str]]] | None = None
    examples: dict[str, Callable[[], None]] = field(default_factory=dict)

    def page_title(self) -> str:
        """現在の画面名を返す。"""
        return self.title() if callable(self.title) else self.title


@cache
def screens() -> dict[str, Screen]:
    """URLをキーに画面を自動登録する。"""
    by_path = {}
    for module in iter_modules(pages.__path__):
        if not module.ispkg or module.name == "login":
            continue
        feature = import_module(f"{pages.__name__}.{module.name}")
        for screen in feature.SCREENS:
            if screen.path in by_path:
                raise ValueError(f"画面のルートが重複しています: {screen.path}")
            by_path[screen.path] = screen
    return by_path


@cache
def guide_examples() -> dict[str, Callable[[], None]]:
    """ガイドで表示する画面例を集める。"""
    return {key: draw for screen in screens().values() for key, draw in screen.examples.items()}


def resolve(path: str) -> Screen | None:
    """固定URLまたは詳細URLに対応する画面を探す。"""
    routes = screens()
    if path in routes:
        return routes[path]
    # 深い操作パスから順に探し、既存の詳細ルートも同じURLで解決する。
    while "/" in path:
        path, _, _ = path.rpartition("/")
        if screen := routes.get(path + "/"):
            return screen
    return None


def menu(user: dict[str, Any]) -> dict[str, list[Screen]]:
    """閲覧者に表示するメニューを順序どおりにまとめる。"""
    groups: dict[str, list[Screen]] = {}
    for screen in sorted(screens().values(), key=lambda item: (item.order, item.path)):
        if screen.group and screen.visible(user):
            entries = groups.setdefault(screen.group, [])
            if screen.menu_paths:
                entries.extend(
                    replace(screen, path=path, title=label) for path, label in screen.menu_paths(user)
                )
            else:
                entries.append(screen)
    return groups
