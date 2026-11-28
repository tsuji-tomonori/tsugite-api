"""人・組織・認証情報の画面テストで使う業務データとDOM操作をまとめる。"""

import asyncio
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

type Module = Callable[[str], Any]
type Record = dict[str, Any]


def content(node: Any) -> str:
    """表示された子要素のテキストを文書順に読む。"""
    return "".join(
        child.data if child.nodeType == child.TEXT_NODE else content(child) for child in node.childNodes
    )


def row_with(dom: Any, label: str) -> Any:
    """指定文字列を表示している表の行を返す。"""
    return next(row for row in dom.getElementsByTagName("tr") if label in content(row))


def person(
    key: str, username: str, email: str, full_name: str | None = None, display_name: str | None = None
) -> Record:
    """名簿に表示する一人分のプロフィールを用意する。"""
    return {
        "subject": key,
        "username": username,
        "email": email,
        "full_name": full_name,
        "display_name": display_name,
    }


def unit(
    key: str, name: str, kind: str = "department", parent: str = "", stopped: bool = False
) -> Record:
    """部署またはプロジェクトの公開API項目を用意する。"""
    return {"id": key, "name": name, "kind": kind, "parent": parent, "stopped": stopped}


def workspace(
    units: Sequence[Record],
    memberships: Sequence[Record] = (),
    *,
    admin: bool = False,
    leads: Sequence[str] = (),
) -> Record:
    """指定した組織・所属と管理範囲でワークスペースの応答を組み立てる。"""
    return {
        "admin": admin,
        "units": units,
        "memberships": list(memberships),
        "leads": list(leads),
        "my_units": [item["id"] for item in units],
        "users": list(memberships),
        "titles": [],
    }


def member(*, admin: bool = False, provider: bool = False) -> Record:
    """画面を操作する利用者の所属・権限を用意する。"""
    return {
        "subject": "operator",
        "personal_project": "private",
        "projects": ["stock"],
        "admin": admin,
        "owners": ["supply"] if provider else [],
        "auditor": False,
        "leads": [],
        "known_projects": ["stock"],
        "known_project_labels": {"stock": "在庫管理"},
        "departments": [],
        "titles": [],
        "targets": {},
    }


class Buttons:
    """描画されたボタンをラベルで選んで擬似クリックする。"""

    def __init__(self, controls: Any) -> None:
        self.draw = controls.btn
        self.callbacks: dict[str, Callable[..., Any]] = {}

    def __call__(self, label: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        if fn is not None:
            self.callbacks[label] = partial(fn, *args)
        return self.draw(label, fn, *args, **kwargs)

    def click(self, label: str) -> None:
        """指定したボタンから画面の非同期操作を実行する。"""
        asyncio.run(self.callbacks[label]())
