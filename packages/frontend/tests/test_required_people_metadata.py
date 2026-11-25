# 利用者属性の定義、値の所属とプロフィール表示を要件・利用手順・組織APIの公開契約から検証する。
import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import (
    Buttons,
    Module,
    Record,
    content,
    member,
    person,
    row_with,
    unit,
    workspace,
)


def metadata_directory(*, admin: bool) -> Record:
    """部署・プロジェクト・任意二項目と兼務者の所属を組織APIの形で用意する。"""
    fields = [
        {"key": "department", "label": "部署", "builtin": True, "public_values": False},
        {"key": "project", "label": "プロジェクト", "builtin": True, "public_values": True},
        {"key": "employer", "label": "所属会社", "builtin": False, "public_values": False},
        {"key": "employment", "label": "雇用区分", "builtin": False, "public_values": True},
    ]
    units = [
        unit("dept", "業務管理部"),
        unit("stock", "在庫移行", "project", "dept"),
        unit("hq", "関西本社", "employer"),
        unit("staff", "社員", "employment"),
        unit("contract", "業務委託", "employment"),
        unit("special", "専門職", "employment", "contract"),
    ]
    person1 = person("operator", "田中", "tanaka@example.test", "田中陽子", "窓口")
    person2 = person("u2", "木村", "kimura@example.test")
    memberships = [
        dict(person1, unit_id="contract", title="連絡係", leader=True, active=True),
        dict(person1, unit_id="hq", title="担当", leader=False, active=True),
        dict(person2, unit_id="staff", title="統括", leader=True, active=True),
    ]
    return dict(
        workspace(units, memberships, admin=admin),
        metadata_fields=fields,
        my_units=["contract", "hq"],
        leads=["contract"],
        users=[person1, person2],
    )


def enter(portal_module: Module, monkeypatch: pytest.MonkeyPatch, path: str, tree: Record) -> Any:
    """現在の利用者の表示範囲を設定し公開ルートを解決する。"""
    ui = portal_module("runtime.portal_ui")
    actor = dict(
        member(admin=tree["admin"]),
        metadata_fields=tree["metadata_fields"],
        metadata={"employment": ["contract"], "employer": ["hq"]},
    )
    ui.ctx.update(workspace=tree, me=actor)
    monkeypatch.setattr(
        portal_module("js").window, "location", SimpleNamespace(hash="#/" + path), raising=False
    )
    return portal_module("routing.screen_registry").resolve(path)


@pytest.mark.parametrize(
    "admin",
    [
        pytest.param(
            True,
            id="admin",
            marks=pytest.mark.case_detail("管理者には属性の追加と任意項目の編集操作が表示される"),
        ),
        pytest.param(
            False,
            id="member",
            marks=pytest.mark.case_detail("利用者には閲覧できる項目と値の公開範囲が表示される"),
        ),
    ],
)
def test_metadata_field_directory(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, admin: bool
) -> None:
    """部署とプロジェクトは使用中のデータパーツ、任意項目は公開設定付きで一覧できる。"""
    tree = metadata_directory(admin=admin)
    screen = enter(portal_module, monkeypatch, "metadata", tree)
    dom = render(screen.view)[1]
    for label in ("部署", "プロジェクト"):
        assert "使用中" in content(row_with(dom, label))
    for label, audience in (("所属会社", "所属者"), ("雇用区分", "全利用者")):
        row = row_with(dom, label)
        assert audience in content(row)
        assert "使用中" not in content(row)
    create = [a for a in dom.getElementsByTagName("a") if "項目を追加" in content(a)]
    assert bool(create) == admin


def test_attribute_navigation_and_values(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """雇用区分から同じ項目の値だけを一覧し、対象グループの詳細を開ける。"""
    tree = metadata_directory(admin=True)
    screen = enter(portal_module, monkeypatch, "attributes/employment", tree)
    actions = portal_module("actions.workspace")
    ui = portal_module("runtime.portal_ui")
    assert ("attributes/employment", "雇用区分") in actions.attribute_menu(ui.ctx["me"])
    first = render(screen.view)[1]
    assert all(name in content(first) for name in ("社員", "業務委託", "専門職"))
    assert "関西本社" not in content(first) and "在庫移行" not in content(first)
    detail = next(
        a.getAttribute("href") for a in first.getElementsByTagName("a") if content(a) == "業務委託"
    )
    next_screen = enter(portal_module, monkeypatch, detail.removeprefix("#/"), tree)
    dom = render(next_screen.view)[1]
    row = row_with(dom, "tanaka@example.test")
    assert "リーダー" in content(row) and "連絡係" in content(row)
    assert "kimura@example.test" not in content(dom)


@pytest.mark.parametrize(
    ("path", "key", "label", "public"),
    [
        pytest.param(
            "metadata/create",
            "skill-type",
            "専門区分",
            True,
            id="new-public",
            marks=pytest.mark.case_detail("新しい分類キーと名称を登録して値の名称を全員に公開する"),
        ),
        pytest.param(
            "metadata/edit/employment",
            "employment",
            "契約区分",
            False,
            id="rename-private",
            marks=pytest.mark.case_detail("既存の分類キーを保ち表示名と値名の公開範囲を変更する"),
        ),
    ],
)
def test_save_attribute_definition(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, path: str, key: str, label: str, public: bool
) -> None:
    """属性項目の保存はキーと表示名、値名の公開範囲を組織APIに渡して一覧に戻れる。"""
    tree = metadata_directory(admin=True)
    screen = enter(portal_module, monkeypatch, path, tree)
    view = portal_module("components.metadata")
    api = portal_module("apis.organization")
    buttons = Buttons(portal_module("components.controls"))
    monkeypatch.setattr(view, "btn", buttons)
    saved = AsyncMock(
        return_value={"key": key, "label": label, "builtin": False, "public_values": public}
    )
    monkeypatch.setattr(api, "save_field", saved)
    monkeypatch.setattr(view, "go", AsyncMock())
    dom = render(screen.view)[1]
    visibility = dom.getElementsByTagName("select")[0]
    selected = next(
        option.getAttribute("value")
        for option in visibility.getElementsByTagName("option")
        if ("全利用者" in content(option)) == public
    )
    inputs = {"metadata-label": label, "metadata-key": key, "metadata-scope": selected}
    monkeypatch.setattr(view, "value", inputs.__getitem__)
    buttons.click("保存")
    saved.assert_awaited_once_with(key, {"label": label, "public_values": public})


def test_profile_lists_assigned_values_and_roles(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """本人のプロフィールは割り当てられた値・役割を表示し、別の利用者だけの値は含めない。"""
    tree = metadata_directory(admin=False)
    screen = enter(portal_module, monkeypatch, "profile", tree)
    api = portal_module("apis.organization")
    user = person("operator", "田中", "tanaka@example.test", "田中陽子", "窓口")
    monkeypatch.setattr(api, "profile", AsyncMock(return_value=dict(user, revision=3)))
    monkeypatch.setattr(api, "workspace", AsyncMock(return_value=tree))
    asyncio.run(screen.load_data("profile"))
    dom = render(screen.view)[1]
    row = row_with(dom, "業務委託")
    assert all(value in content(row) for value in ("雇用区分", "リーダー", "連絡係"))
    assert "関西本社" in content(dom) and "社員" not in content(dom)


def test_create_attribute_value_with_parent(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """属性値の追加では同一項目の上位値を選び、任意属性として新しいグループを登録する。"""
    tree = metadata_directory(admin=True)
    screen = enter(portal_module, monkeypatch, "attributes/employment/create", tree)
    view = portal_module("components.workspace_views")
    api = portal_module("apis.organization")
    buttons = Buttons(portal_module("components.controls"))
    monkeypatch.setattr(view, "btn", buttons)
    monkeypatch.setattr(view, "go", AsyncMock())
    save = AsyncMock(return_value=unit("dispatch", "派遣", "employment", "contract"))
    monkeypatch.setattr(api, "save_unit", save)
    dom = render(screen.view)[1]
    options = {o.getAttribute("value") for o in dom.getElementsByTagName("option")}
    assert {"staff", "contract", "special"} <= options
    assert "dept" not in options and "hq" not in options and "stock" not in options
    values = {"org-unit-name": "派遣", "org-unit-id": "dispatch", "org-parent": "contract"}
    monkeypatch.setattr(view, "value", values.__getitem__)
    buttons.click("保存")
    assert save.await_args is not None
    key, data = save.await_args.args
    assert str(key) == "dispatch" and data["kind"] == "employment"
    assert data["name"] == "派遣" and data["parent"] == "contract"


def test_assign_role_in_attribute_group(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """任意属性の値に利用者を割り当てると、その値を対象に役割名とリーダー権限を保存する。"""
    tree = metadata_directory(admin=True)
    screen = enter(portal_module, monkeypatch, "attributes/employment/member/contract", tree)
    view = portal_module("components.workspace_members")
    api = portal_module("apis.organization")
    buttons = Buttons(portal_module("components.controls"))
    monkeypatch.setattr(view, "btn", buttons)
    monkeypatch.setattr(view, "go", AsyncMock())
    save = AsyncMock(return_value={})
    monkeypatch.setattr(api, "membership", save)
    dom = render(screen.view)[1]
    assert any(o.getAttribute("value") == "u2" for o in dom.getElementsByTagName("option"))
    values = {"org-subject": "u2", "org-title": "契約窓口", "org-leader": "yes"}
    monkeypatch.setattr(view, "value", values.__getitem__)
    buttons.click("所属を保存")
    assert save.await_args is not None
    body = save.await_args.args[0]
    assert body["subject"] == "u2" and body["unit_id"] == "contract"
    assert body["title"] == "契約窓口" and body["leader"] is True


def test_public_group_value_without_roster(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """公開された値名は一覧で読めるが、名簿が提供されていない値の利用者や役割は表示されない。"""
    tree = metadata_directory(admin=False)
    tree.update(leads=[], memberships=[], my_units=[], users=[])
    screen = enter(portal_module, monkeypatch, "attributes/employment", tree)
    dom = render(screen.view)[1]
    assert "社員" in content(dom) and "業務委託" in content(dom)
    detail = enter(portal_module, monkeypatch, "attributes/employment/detail/staff", tree)
    contents = content(render(detail.view)[1])
    assert "社員" in contents and "kimura@example.test" not in contents and "統括" not in contents


def test_profile_with_no_values(portal_module: Module) -> None:
    """プロフィールに本人の割当てがなければ他人の属性値や役割を表示しない。"""
    tree = metadata_directory(admin=False)
    tree.update(my_units=[], memberships=[r for r in tree["memberships"] if r["subject"] == "u2"])
    profile = portal_module("components.profile")
    portal_module("runtime.portal_ui").ctx["me"] = dict(
        member(), metadata={}, metadata_fields=tree["metadata_fields"]
    )
    dom = render(profile.person_metadata, tree, "operator")[1]
    assert "統括" not in content(dom)
    assert "社員" not in content(dom)
