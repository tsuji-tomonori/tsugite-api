"""画面モジュールからルートとナビゲーションを組み立てる。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from functools import cache
from importlib import import_module
from pkgutil import iter_modules

import portal_pages


@dataclass(frozen=True)
class Screen:
    path: str
    title: str | Callable[[], str]
    view: Callable[[], None]
    load_data: Callable[[str], Awaitable[None]] | None = None
    group: str = ""
    order: int = 0
    visible: Callable[[dict], bool] = lambda user: True
    parent: str = ""
    description: str = ""
    heading_action: Callable[[], None] | None = None
    own_heading: bool = False
    clear_on_load: tuple[str, ...] = ()

    menu_paths: Callable[[dict], list[tuple[str, str]]] | None = None
    examples: dict[str, Callable[[], None]] = field(default_factory=dict)

    def page_title(self):
        return self.title() if callable(self.title) else self.title


@cache
def screens():
    by_path = {}
    for module in iter_modules(portal_pages.__path__):
        if module.name.startswith("_"):
            continue
        feature = import_module(f"{portal_pages.__name__}.{module.name}")
        for screen in feature.SCREENS:
            if screen.path in by_path:
                raise ValueError(f"画面のルートが重複しています: {screen.path}")
            by_path[screen.path] = screen
    return by_path


@cache
def guide_examples():
    return {key: draw for screen in screens().values() for key, draw in screen.examples.items()}


def resolve(path):
    routes = screens()
    if path in routes:
        return routes[path]
    prefix, slash, _ = path.partition("/")
    return routes.get(prefix + slash)


def menu(user):
    groups = {}
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
