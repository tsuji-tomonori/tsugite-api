# 部署・プロジェクトの一覧と所属を、画面仕様と組織APIの応答契約に基づいて検証する。

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs

import pytest
from test_components import render
from test_required_people_support import Buttons, Module, content, member, person, unit, workspace


@pytest.mark.parametrize(
    ("number", "first", "last", "outside"),
    [
        pytest.param(
            1,
            "開発01",
            "開発10",
            "開発11",
            id="first",
            marks=pytest.mark.case_detail("最初の10件を部署の表に表示する"),
        ),
        pytest.param(
            2,
            "開発11",
            "開発12",
            "開発10",
            id="last",
            marks=pytest.mark.case_detail("次ページには残り2件だけ表示する"),
        ),
    ],
)
def test_department_directory_pages(
    portal_module: Module, number: int, first: str, last: str, outside: str
) -> None:
    """部署の一覧を開くと部署だけを10件ずつ表示し、名称から詳細へ進める。"""
    views = portal_module("components.workspace_views")
    units = [unit(f"dept{i:02}", f"開発{i:02}") for i in range(1, 13)]
    units.append(unit("project-x", "受発注開発", "project"))
    by_id = {item["id"]: item for item in units}
    dom = render(
        views.list_view,
        "departments",
        "部署",
        "department",
        workspace(units),
        by_id,
        views.unit_paths(by_id),
        number,
    )[1]
    links = [content(link) for link in dom.getElementsByTagName("a")]
    assert first in links and last in links
    assert outside not in links and "受発注開発" not in links
    names = [name for name in links if name.startswith("開発")]
    assert len(names) == (10 if number == 1 else 2)


def test_project_directory_has_link_and_state(portal_module: Module) -> None:
    """プロジェクトの表で所属先の名称と状態を確認し、詳細画面を選べる。"""
    views = portal_module("components.workspace_views")
    parent = unit("dept", "物流統括")
    project = unit("stock", "在庫移行", kind="project", parent="dept", stopped=True)
    by_id = {"dept": parent, "stock": project}
    dom = render(
        views.list_view,
        "projects",
        "プロジェクト",
        "project",
        workspace([parent, project]),
        by_id,
        views.unit_paths(by_id),
        1,
    )[1]
    row = next(row for row in dom.getElementsByTagName("tr") if "在庫移行" in content(row))
    assert "停止" in content(row)
    assert any("stock" in a.getAttribute("href") for a in row.getElementsByTagName("a"))


def test_directory_member_details(portal_module: Module) -> None:
    """直接所属する利用者についてメール、氏名、表示名と役職を同じ一覧で読める。"""
    members = portal_module("components.workspace_members")
    department = unit("qa", "品質管理")
    analyst = person("u-01", "qa-user", "qa@example.test", "田中花子", "品質窓口")
    analyst.update(unit_id="qa", title="主任", leader=True, active=True)
    dom = render(members.members_view, "departments", department, workspace([department], [analyst]))[1]
    row = next(row for row in dom.getElementsByTagName("tr") if "qa@example.test" in content(row))
    for text in ("田中花子", "品質窓口", "主任"):
        assert text in content(row)


def test_monitor_totals_and_breakdowns(portal_module: Module) -> None:
    """モニタリングで呼び出し数・エラー数とAPI別、プロジェクト別の内訳を照合できる。"""
    monitor = portal_module("components.workspace_monitor")
    ui = portal_module("runtime.portal_ui")
    department = unit("dept", "物流部")
    ui.ctx["workspace_usage"] = {
        "unit_id": "dept",
        "members": [],
        "calls": 29,
        "errors": 3,
        "by_project": [{"project": "倉庫", "calls": 19}, {"project": "配送", "calls": 10}],
        "by_api": [
            {"asset_id": "inventory", "name": "在庫照会", "calls": 24},
            {"asset_id": "contacts", "name": "宛先照会", "calls": 5},
        ],
    }
    dom = render(monitor.monitoring_view, department, {})[1]
    display = " ".join(content(dom).split())
    for name, count in (
        ("呼び出し", 29),
        ("エラー", 3),
        ("倉庫", 19),
        ("配送", 10),
        ("在庫照会", 24),
        ("宛先照会", 5),
    ):
        assert f"{name}{count} 件" in display


def test_membership_editor_shows_current_role(portal_module: Module) -> None:
    """所属を編集すると選んだ利用者の役職とリーダー設定が入力済みになる。"""
    member_ui = portal_module("components.workspace_members")
    project = unit("ledger", "予算管理", "project")
    chief = person("chief", "accounting", "chief@example.test", "日野徹", "会計担当")
    chief.update(unit_id="ledger", leader=True, title="会計主任", active=True)
    dom = render(
        member_ui.membership_editor, "projects", project, workspace([project], [chief]), "chief"
    )[1]
    assert "chief@example.test" in content(dom)
    assert any(node.getAttribute("value") == "会計主任" for node in dom.getElementsByTagName("input"))
    selected = [content(o) for o in dom.getElementsByTagName("option") if o.hasAttribute("selected")]
    assert "リーダー" in selected


def test_unit_editor_offers_parent_departments(portal_module: Module) -> None:
    """新規プロジェクトには管轄部署を設定でき、部署を未指定にもできる。"""
    views = portal_module("components.workspace_views")
    units = [
        unit("head", "事業本部"),
        unit("dept", "経理部", parent="head"),
        unit("other", "別プロジェクト", "project", "head"),
    ]
    by_id = {item["id"]: item for item in units}
    dom = render(
        views.unit_editor, "projects", "project", "プロジェクト", by_id, views.unit_paths(by_id)
    )[1]
    options = {
        (option.getAttribute("value"), content(option)) for option in dom.getElementsByTagName("option")
    }
    assert any(value == "" for value, _ in options)
    assert any(value == "dept" and "経理部" in name for value, name in options)
    assert any(value == "head" and "事業本部" in name for value, name in options)
    assert all(value != "other" for value, _ in options)


@pytest.mark.parametrize(
    ("is_admin", "root", "key", "heading"),
    [
        pytest.param(
            True,
            "departments",
            "dept",
            "物流本部",
            id="department-admin",
            marks=pytest.mark.case_detail("管理者が部署名を選ぶと物流本部の詳細が開く"),
        ),
        pytest.param(
            False,
            "projects",
            "stock",
            "在庫移行",
            id="project-member",
            marks=pytest.mark.case_detail("所属プロジェクト名を選ぶと在庫移行の詳細が開く"),
        ),
    ],
)
def test_detail_from_directory(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    is_admin: bool,
    root: str,
    key: str,
    heading: str,
) -> None:
    """一覧の名称リンクを開くと対象組織の所属と状態をその場で確認できる。"""

    ui = portal_module("runtime.portal_ui")
    view = portal_module("components.workspace")
    registry = portal_module("routing.screen_registry")
    js = portal_module("js")
    department = unit("dept", "物流本部")
    project = unit("stock", "在庫移行", "project", "dept")
    analyst = person("u-1", "main", "reader@example.test", "森恵", "相談窓口")
    analyst.update(unit_id=key, title="担当", leader=False, active=True)
    me = {"subject": "u-1", "admin": is_admin, "owners": [], "leads": [], "projects": ["stock"]}
    ui.ctx.update(workspace=workspace([department, project], [analyst], admin=is_admin), me=me)
    route = f"{root}/detail/{key}"
    monkeypatch.setattr(js.window, "location", SimpleNamespace(hash=f"#/{route}"), raising=False)
    screen = registry.resolve(route)
    dom = render(screen.view)[1]
    assert "reader@example.test" in content(dom)
    assert "相談窓口" in content(dom)
    assert heading in content(dom) or heading in view.page_title()


@pytest.mark.parametrize(
    ("is_new", "leader", "subject"),
    [
        pytest.param(
            True,
            True,
            "new-user",
            id="add-lead",
            marks=pytest.mark.case_detail("新規の所属にリーダー権限と役職を付ける"),
        ),
        pytest.param(
            False,
            False,
            "old-user",
            id="update-role",
            marks=pytest.mark.case_detail("既存メンバーの役職を変え、リーダー指定を外す"),
        ),
    ],
)
def test_save_membership_for_selected_unit(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, is_new: bool, leader: bool, subject: str
) -> None:
    """所属編集画面で保存すると対象者、組織、役職とリーダー権限を指定して所属を更新する。"""

    views = portal_module("components.workspace_members")
    ctrl = portal_module("components.controls")
    org = portal_module("apis.organization")
    buttons = Buttons(ctrl)
    project = unit("stock", "在庫移行", "project")
    candidate = person(subject, "logistics", "staff@example.test")
    assigned = dict(candidate, unit_id="stock", title="担当", leader=True, active=True)
    data = workspace([project], [] if is_new else [assigned], admin=True)
    data["users"] = [candidate]
    values = {"org-subject": subject, "org-title": "物流主任", "org-leader": "yes" if leader else "no"}
    monkeypatch.setattr(views, "value", values.__getitem__)
    monkeypatch.setattr(views, "btn", buttons)
    monkeypatch.setattr(views, "go", AsyncMock())
    save = AsyncMock(return_value={})
    monkeypatch.setattr(org, "membership", save)
    render(views.membership_editor, "projects", project, data, None if is_new else subject)
    buttons.click("所属を保存")
    assert save.await_args is not None
    body = save.await_args.args[0]
    for name, expected in {
        "unit_id": "stock",
        "subject": subject,
        "title": "物流主任",
        "leader": leader,
    }.items():
        assert body[name] == expected


def test_edit_project_label_and_parent(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """プロジェクトの基本設定を保存すると表示名と管轄部署を同じプロジェクトに反映する。"""

    views = portal_module("components.workspace_views")
    ctrl = portal_module("components.controls")
    org = portal_module("apis.organization")
    buttons = Buttons(ctrl)
    project = unit("stock", "棚卸", "project")
    department = unit("dept", "物流部")
    by_id = {"stock": project, "dept": department}
    monkeypatch.setattr(views, "btn", buttons)
    monkeypatch.setattr(views, "go", AsyncMock())
    monkeypatch.setattr(views, "value", {"org-unit-name": "物流棚卸", "org-parent": "dept"}.__getitem__)
    save = AsyncMock(return_value=dict(project, name="物流棚卸", parent="dept"))
    monkeypatch.setattr(org, "save_unit", save)
    render(
        views.unit_editor, "projects", "project", "プロジェクト", by_id, views.unit_paths(by_id), project
    )
    buttons.click("保存")
    assert save.await_args is not None
    key, body = save.await_args.args
    assert key == "stock"
    assert body["name"] == "物流棚卸" and body["parent"] == "dept"


@pytest.mark.parametrize(
    ("before", "expected"),
    [
        pytest.param(
            False, True, id="stop", marks=pytest.mark.case_detail("対象組織の利用を一時停止する")
        ),
        pytest.param(
            True,
            False,
            id="resume",
            marks=pytest.mark.case_detail("停止している対象組織の利用を再開する"),
        ),
    ],
)
def test_workspace_use_state(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, before: bool, expected: bool
) -> None:
    """リーダーが部署の利用を停止・再開すると、その部署に新しい利用状態を適用する。"""

    actions = portal_module("actions.workspace")
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: True, raising=False)
    org = portal_module("apis.organization")
    save = AsyncMock(return_value={})
    monkeypatch.setattr(org, "unit_state", save)
    monkeypatch.setattr(actions, "load", AsyncMock())
    asyncio.run(actions.toggle(unit("logistics", "物流部", stopped=before)))
    assert save.await_args is not None
    endpoint, state = save.await_args.args
    assert "logistics" in endpoint and state == {"stopped": expected}


@pytest.mark.parametrize(
    ("operation", "confirm"),
    [
        pytest.param(
            "transfer",
            True,
            id="transfer",
            marks=pytest.mark.case_detail("対象部署と引継ぎ先を確認して移管する"),
        ),
        pytest.param(
            "transfer",
            False,
            id="cancel-transfer",
            marks=pytest.mark.case_detail("移管の確認で取りやめれば所属を移さない"),
        ),
        pytest.param(
            "remove",
            True,
            id="delete",
            marks=pytest.mark.case_detail("空の部署を選んで削除を確定できる"),
        ),
        pytest.param(
            "remove",
            False,
            id="cancel-delete",
            marks=pytest.mark.case_detail("部署の削除確認で取りやめれば削除しない"),
        ),
    ],
)
def test_confirm_organization_retirement(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, operation: str, confirm: bool
) -> None:
    """部署の移管・削除では対象を確認し、確定された操作だけを組織APIに送る。"""

    view = portal_module("components.workspace_views")
    api = portal_module("apis.organization")
    ctrl = portal_module("components.controls")
    buttons = Buttons(ctrl)
    source = unit("closed", "業務企画部")
    destination = unit("successor", "営業部")
    by_id = {"closed": source, "successor": destination}
    monkeypatch.setattr(view, "btn", buttons)
    monkeypatch.setattr(view, "value", {"unit-destination": "successor"}.__getitem__)
    monkeypatch.setattr(view, "go", AsyncMock())
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: confirm, raising=False)
    submit = AsyncMock(return_value={})
    monkeypatch.setattr(api, "transfer_unit" if operation == "transfer" else "delete_unit", submit)
    dom = render(view.retirement_form, "departments", "部署", source, by_id, view.unit_paths(by_id))[1]
    assert "営業部" in content(dom)
    buttons.click("部署を移管" if operation == "transfer" else "部署を削除")
    if not confirm:
        submit.assert_not_awaited()
        return
    assert submit.await_args is not None
    assert "closed" in submit.await_args.args[0]
    if operation == "transfer":
        assert "successor" in submit.await_args.args[1].values()


@pytest.mark.parametrize(
    "confirm",
    [
        pytest.param(
            True,
            id="remove",
            marks=pytest.mark.case_detail("選択した組織でだけメンバーの所属を解除する"),
        ),
        pytest.param(
            False,
            id="cancel",
            marks=pytest.mark.case_detail("所属解除を取りやめるとメンバーは組織に残る"),
        ),
    ],
)
def test_remove_membership_from_detail(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, confirm: bool
) -> None:
    """所属詳細に表示された解除操作を確定した場合だけ、選んだ組織と利用者の関連を解除する。"""

    views = portal_module("components.workspace_members")
    ctrl = portal_module("components.controls")
    org = portal_module("apis.organization")
    project = unit("stock", "在庫移行", "project")
    member = dict(
        person("u-01", "stock-user", "staff@example.test"), unit_id="stock", title="担当", leader=False
    )
    data = workspace([project], [member], admin=True)
    buttons = Buttons(ctrl)
    monkeypatch.setattr(views, "btn", buttons)
    monkeypatch.setattr(views, "load", AsyncMock())
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: confirm, raising=False)
    remove = AsyncMock(return_value={})
    monkeypatch.setattr(org, "remove_membership", remove)
    dom = render(views.members_view, "projects", project, data)[1]
    assert "staff@example.test" in content(dom)
    buttons.click("所属を解除")
    if confirm:
        assert remove.await_args is not None
        parameters = parse_qs(remove.await_args.args[0].lstrip("?"))
        assert parameters["subject"] == ["u-01"] and parameters["unit_id"] == ["stock"]
    else:
        remove.assert_not_awaited()


def test_load_more_candidates_for_membership(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """管理者が所属候補を読み込むと、追加の登録ユーザーを対象組織の所属先に選べる。"""

    view = portal_module("components.workspace_members")
    ctrl = portal_module("components.controls")
    org = portal_module("apis.organization")
    project = unit("stock", "在庫移行", "project")
    tree = workspace([project], [], admin=True)
    buttons = Buttons(ctrl)
    monkeypatch.setattr(view, "btn", buttons)
    values = {"org-subject": "", "org-title": "主任", "org-leader": "no"}
    monkeypatch.setattr(view, "value", values.__getitem__)
    candidate = person("u-01", "stock-user", "staff@example.test", "森恵", "連絡窓口")
    get = AsyncMock(return_value={"items": [candidate], "next": "", "projects": ["stock"]})
    monkeypatch.setattr(org, "members", get)
    render(view.membership_editor, "projects", project, tree, None)
    buttons.click("登録ユーザーを読み込む")
    get.assert_awaited_once()
    ui = portal_module("runtime.portal_ui")
    dom = render(
        lambda: view.membership_editor("projects", project, tree, None, draft=ui.ctx.get("member_form"))
    )[1]
    assert any(
        option.getAttribute("value") == "u-01" and "staff@example.test" in content(option)
        for option in dom.getElementsByTagName("option")
    )


def test_empty_project_directory(portal_module: Module) -> None:
    """最後の所属を外れた利用者のプロジェクト一覧は0件となり、他組織の名前を表示しない。"""
    views = portal_module("components.workspace_views")
    department = unit("dept", "物流本部")
    by_id = {"dept": department}
    dom = render(
        views.list_view,
        "projects",
        "プロジェクト",
        "project",
        workspace([department]),
        by_id,
        views.unit_paths(by_id),
        1,
    )[1]
    assert "0 件" in content(dom)
    assert not dom.getElementsByTagName("tr")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(
            "projects/create",
            "名称",
            id="create",
            marks=pytest.mark.case_detail("作成画面で新しいプロジェクトの名称を入力する"),
        ),
        pytest.param(
            "projects/edit/stock",
            "棚卸移行",
            id="edit",
            marks=pytest.mark.case_detail("対象プロジェクトの現在の基本設定から編集を始める"),
        ),
        pytest.param(
            "projects/member/stock",
            "所属を保存",
            id="add-member",
            marks=pytest.mark.case_detail("所属追加の画面から既存利用者を選べる"),
        ),
        pytest.param(
            "projects/member/stock/u-1",
            "調査班長",
            id="edit-member",
            marks=pytest.mark.case_detail("所属編集の画面から対象者の役職を確認する"),
        ),
        pytest.param(
            "projects/monitor/stock",
            "棚卸明細",
            id="monitor",
            marks=pytest.mark.case_detail(
                "モニタリング画面で選択したプロジェクトのAPI利用実績を取得する"
            ),
        ),
    ],
)
def test_workspace_screens_load_selected_project(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, path: str, expected: str
) -> None:
    """管理画面のリンク先が対象組織の情報を読み込み、選んだ仕事に対応する画面を表示する。"""

    ui = portal_module("runtime.portal_ui")
    pages = portal_module("routing.screen_registry")
    org = portal_module("apis.organization")
    js = portal_module("js")
    project = unit("stock", "棚卸移行", "project")
    analyst = dict(
        person("u-1", "担当者", "analyst@example.test"), title="調査班長", unit_id="stock", leader=True
    )
    data = workspace([project], [analyst], admin=True)
    session = member(admin=True)
    ui.ctx.update(me=session)
    monkeypatch.setattr(js.window, "location", SimpleNamespace(hash="#/" + path), raising=False)
    monkeypatch.setattr(org, "workspace", AsyncMock(return_value=data))
    get_usage = AsyncMock(
        return_value={
            "unit_id": "stock",
            "members": [analyst],
            "calls": 41,
            "errors": 1,
            "by_project": [{"project": "stock", "calls": 41}],
            "by_api": [{"asset_id": "inv", "name": "棚卸明細", "calls": 41}],
        }
    )
    monkeypatch.setattr(org, "unit_usage", get_usage)
    screen = pages.resolve(path)
    asyncio.run(screen.load_data(path))
    dom = render(screen.view)[1]
    assert expected in dom.toxml()
    if path == "projects/monitor/stock":
        get_usage.assert_awaited_once()


@pytest.mark.parametrize(
    ("label", "kind"),
    [
        pytest.param(
            "部署",
            "department",
            id="department",
            marks=pytest.mark.case_detail("上位部署を持つ新しい部署を作成する"),
        ),
        pytest.param(
            "プロジェクト",
            "project",
            id="project",
            marks=pytest.mark.case_detail("管轄部署を持つ新しいプロジェクトを作成する"),
        ),
    ],
)
def test_create_named_organization(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, label: str, kind: str
) -> None:
    """新規作成では利用者が指定した識別子・名称と親部署を選んだ組織種別で保存する。"""

    view = portal_module("components.workspace_views")
    api = portal_module("apis.organization")
    ctrl = portal_module("components.controls")
    buttons = Buttons(ctrl)
    parent = unit("head", "管理本部")
    tree = {"head": parent}
    root = "projects" if kind == "project" else "departments"
    monkeypatch.setattr(view, "btn", buttons)
    monkeypatch.setattr(view, "go", AsyncMock())
    values = {"org-unit-id": "shipment", "org-unit-name": "物流改革", "org-parent": "head"}
    monkeypatch.setattr(view, "value", values.__getitem__)
    save = AsyncMock(return_value=unit("shipment", "物流改革", kind, "head"))
    monkeypatch.setattr(api, "save_unit", save)
    render(view.unit_editor, root, kind, label, tree, view.unit_paths(tree))
    buttons.click("保存")
    assert save.await_args is not None
    key, data = save.await_args.args
    assert (
        key == "shipment"
        and data["kind"] == kind
        and data["parent"] == "head"
        and data["name"] == "物流改革"
    )
