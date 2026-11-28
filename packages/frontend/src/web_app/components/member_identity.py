# ユーザー一覧と選択候補にログイン名とプロフィールの氏名を表示する。
from typing import Any

from puepy import t


def full_name_cell(person: dict[str, Any]) -> None:
    """氏名を主表示し、異なる表示名があれば添える。"""
    name = person.get("full_name")
    with t.td():
        t.span(name or "未登録")
        alias = person.get("display_name")
        if alias and alias != name:
            t.div(f"表示名　{alias}", classes="muted")


def person_label(person: dict[str, Any]) -> str:
    """候補をユーザー名と氏名で区別し、別の表示名やメールも併記する。"""
    username = person.get("username") or person["subject"]
    details = [person.get("full_name") or "氏名未登録"]
    for value in (person.get("display_name"), person.get("email")):
        if value and value != username and value not in details:
            details.append(value)
    return f"{username}（{'、'.join(details)}）"
