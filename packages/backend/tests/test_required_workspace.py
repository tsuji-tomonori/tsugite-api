# 組織編成・兼務・担当者の交代を、公開APIから利用者が確認できる結果で検証する。
import pytest

from tests.support.catalog import headers


def _unit(portal, admin, key, kind, name, parent=""):
    response = portal.put(
        f"/api/workspace/units/{key}",
        headers=admin,
        json={"kind": kind, "name": name, "parent": parent},
    )
    assert response.status_code == 200
    result = response.json()
    assert (result["id"], result["kind"], result["name"], result["parent"]) == (
        key,
        kind,
        name,
        parent,
    )
    return result


def _assign(portal, admin, subject, unit_id, title, leader):
    membership = {"subject": subject, "unit_id": unit_id, "title": title, "leader": leader}
    response = portal.put("/api/workspace/memberships", headers=admin, json=membership)
    assert response.status_code == 200
    assert response.json() == membership


def test_direct_and_concurrent_memberships(portal):
    """上位部署とプロジェクトを兼務してから片方を外しても、残る所属の役職と管理権限を保持する。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    _unit(portal, admin, "planning", "department", "企画部")
    _unit(portal, admin, "research", "department", "調査課", "planning")
    _unit(portal, admin, "pilot", "project", "実証プロジェクト", "research")
    _assign(portal, admin, subject, "planning", "部長", True)
    _assign(portal, admin, subject, "pilot", "調査員", False)
    usage = portal.get("/api/workspace/units/planning/usage", headers=user)
    assert usage.status_code == 200
    assert usage.json()["unit_id"] == "planning"
    assert any(
        item["subject"] == subject and item["title"] == "部長" and item["leader"]
        for item in usage.json()["members"]
    )
    assert usage.json()["calls"] == usage.json()["errors"] == 0
    _assign(portal, admin, subject, "pilot", "主任", True)
    response = portal.delete(
        "/api/workspace/memberships",
        headers=admin,
        params={"subject": subject, "unit_id": "planning"},
    )
    assert response.status_code == 200
    assert response.json()["removed"]
    workspace = portal.get("/api/workspace", headers=user).json()
    assert "planning" not in workspace["my_units"]
    assert "pilot" in workspace["my_units"] and "pilot" in workspace["leads"]
    members = portal.get("/api/workspace/units/pilot/usage", headers=user).json()["members"]
    assert [(m["subject"], m["title"], m["leader"]) for m in members] == [(subject, "主任", True)]


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param(
            "project",
            id="project",
            marks=pytest.mark.case_detail("プロジェクトの停止と再開を一覧に反映する"),
        ),
        pytest.param(
            "department",
            id="department",
            marks=pytest.mark.case_detail("部署の停止と再開を一覧に反映する"),
        ),
    ],
)
def test_unit_lifecycle(portal, kind):
    """新しい組織を改名し、リーダーが停止・再開すると、一覧から各時点の状態を確認できる。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    url = "/api/workspace/units/renewal"
    assert _unit(portal, admin, "renewal", kind, "新設")["stopped"] is False
    _unit(portal, admin, "renewal", kind, "運用")
    _assign(portal, admin, subject, "renewal", "責任者", True)
    for stopped in (True, False):
        response = portal.put(f"{url}/state", headers=user, json={"stopped": stopped})
        assert response.status_code == 200
        assert response.json()["stopped"] is stopped
        units = portal.get("/api/workspace", headers=admin).json()["units"]
        current = next(unit for unit in units if unit["id"] == "renewal")
        assert current["name"] == "運用" and current["stopped"] is stopped


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param(
            "project",
            id="project",
            marks=pytest.mark.case_detail("プロジェクトの所属を移管先に引き継ぐ"),
        ),
        pytest.param(
            "department",
            id="department",
            marks=pytest.mark.case_detail("部署の所属と配下の組織を移管先に引き継ぐ"),
        ),
    ],
)
def test_transfer_of_affiliated_unit(portal, kind):
    """所属のある組織は同種の移管先に統合でき、旧組織は一覧から消える。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    for key, name in (("old-group", "旧組織"), ("new-group", "新組織")):
        _unit(portal, admin, key, kind, name)
    if kind == "department":
        _unit(portal, admin, "child-group", "project", "移管対象プロジェクト", "old-group")
    _assign(portal, admin, subject, "old-group", "担当", True)
    response = portal.post(
        "/api/workspace/units/old-group/transfer", headers=admin, json={"destination": "new-group"}
    )
    assert response.status_code == 200
    assert response.json()["removed"]
    workspace = portal.get("/api/workspace", headers=admin).json()
    units = {unit["id"]: unit for unit in workspace["units"]}
    assert "new-group" in units and "old-group" not in units
    if kind == "department":
        assert units["child-group"]["parent"] == "new-group"
    assert any(
        m["unit_id"] == "new-group" and m["subject"] == subject and m["leader"] and m["title"] == "担当"
        for m in workspace["memberships"]
    )


def test_empty_unit_can_be_removed(portal):
    """利用を開始する前に空の組織を廃止すると、組織一覧に表示されなくなる。"""
    admin = headers(portal, "admin")
    _unit(portal, admin, "closed", "department", "廃止予定")
    response = portal.delete("/api/workspace/units/closed", headers=admin)
    assert response.status_code == 200
    assert response.json()["removed"]
    units = portal.get("/api/workspace", headers=admin).json()["units"]
    assert "closed" not in {unit["id"] for unit in units}


def test_in_use_department_requires_transfer(portal):
    """子部署とプロジェクトが残る部署は削除できず、移管後は両方の親が移管先に変わる。"""
    admin = headers(portal, "admin")
    _unit(portal, admin, "source", "department", "旧部門")
    _unit(portal, admin, "successor", "department", "統合部門")
    _unit(portal, admin, "section", "department", "子部署", "source")
    _unit(portal, admin, "dispatch", "project", "担当案件", "source")
    source_url = "/api/workspace/units/source"
    conflict = portal.delete(source_url, headers=admin)
    assert conflict.status_code == 409 and conflict.json()["detail"]
    before = portal.get("/api/workspace", headers=admin).json()["units"]
    assert {u["id"] for u in before if u["parent"] == "source"} == {"section", "dispatch"}
    moved = portal.post(f"{source_url}/transfer", headers=admin, json={"destination": "successor"})
    assert moved.status_code == 200 and moved.json()["removed"], moved.json()
    after = portal.get("/api/workspace", headers=admin).json()["units"]
    assert {u["id"] for u in after if u["parent"] == "successor"} == {"section", "dispatch"}
    assert all(u["id"] != "source" for u in after)


@pytest.mark.parametrize(
    "destination",
    [
        pytest.param(
            "source",
            id="same-unit",
            marks=pytest.mark.case_detail("移管元自身を指定しても組織を消さない"),
        ),
        pytest.param(
            "child",
            id="descendant",
            marks=pytest.mark.case_detail("子孫の部署を移管先にして階層を循環させない"),
        ),
        pytest.param(
            "project",
            id="different-kind",
            marks=pytest.mark.case_detail(
                "部署の後継にプロジェクトを指定した場合に部署の所属を維持する"
            ),
        ),
        pytest.param(
            "unknown",
            id="missing",
            marks=pytest.mark.case_detail("未登録の移管先へ組織や所属を移さない"),
        ),
    ],
)
def test_invalid_transfer_preserves_directory(portal, destination):
    """移管先が使えない場合は変更を拒み、元の組織、親子関係、所属をすべて保持する。"""
    admin = headers(portal, "admin")
    subject = portal.get("/api/me", headers=headers(portal, "consumer")).json()["subject"]
    _unit(portal, admin, "source", "department", "部")
    _unit(portal, admin, "child", "department", "課", "source")
    _unit(portal, admin, "project", "project", "企画", "source")
    _assign(portal, admin, subject, "source", "担当", False)
    before = portal.get("/api/workspace", headers=admin).json()
    invalid = portal.post(
        "/api/workspace/units/source/transfer", headers=admin, json={"destination": destination}
    )
    assert invalid.status_code in (404, 409, 422) and invalid.json()["detail"]
    after = portal.get("/api/workspace", headers=admin).json()
    assert after["units"] == before["units"] and after["memberships"] == before["memberships"]


def test_conflicting_transfer_keeps_both_projects(portal):
    """重複した所属で移管が競合した場合は、両プロジェクトの既存の所属を保持する。"""
    admin = headers(portal, "admin")
    for key in ("first", "second"):
        _unit(portal, admin, key, "project", key)
    consumer = portal.get("/api/me", headers=headers(portal, "consumer")).json()["subject"]
    provider = portal.get("/api/me", headers=headers(portal, "provider")).json()["subject"]
    _assign(portal, admin, consumer, "first", "主任", False)
    _assign(portal, admin, consumer, "second", "主任", False)
    _assign(portal, admin, provider, "second", "リーダー", True)
    conflict = portal.post(
        "/api/workspace/units/first/transfer", headers=admin, json={"destination": "second"}
    )
    assert conflict.status_code == 409 and conflict.json()["detail"]
    still_present = portal.get("/api/workspace/units/first/usage", headers=admin).json()["members"]
    assert [m["subject"] for m in still_present] == [consumer]
    destination = portal.get("/api/workspace/units/second/usage", headers=admin).json()["members"]
    assert sorted(m["subject"] for m in destination) == sorted([consumer, provider])

    removed = portal.delete(
        "/api/workspace/memberships",
        headers=admin,
        params={"subject": consumer, "unit_id": "second"},
    )
    assert removed.status_code == 200 and removed.json()["removed"]
    listed = portal.get("/api/workspace/units/second/usage", headers=admin).json()["members"]
    assert not any(m["subject"] == consumer and m.get("active", True) for m in listed)
    retried = portal.post(
        "/api/workspace/units/first/transfer", headers=admin, json={"destination": "second"}
    )
    assert retried.status_code == 200, retried.json()
    members = portal.get("/api/workspace/units/second/usage", headers=admin).json()["members"]
    assert sorted(m["subject"] for m in members if m.get("active", True)) == sorted([consumer, provider])


@pytest.mark.parametrize(
    "parent",
    [
        pytest.param(
            "division", id="self", marks=pytest.mark.case_detail("部署自身を親にする編集を拒否する")
        ),
        pytest.param(
            "section", id="child", marks=pytest.mark.case_detail("子部署を親にする編集を拒否する")
        ),
        pytest.param(
            "planning-project",
            id="project",
            marks=pytest.mark.case_detail("プロジェクトを部署の親にする編集を拒否する"),
        ),
        pytest.param(
            "unknown-division",
            id="missing",
            marks=pytest.mark.case_detail("存在しない部署への付け替えを拒否する"),
        ),
    ],
)
def test_invalid_parent_keeps_hierarchy(portal, parent):
    """親を変更できないとき、既存の部署名と親子関係は維持される。"""
    admin = headers(portal, "admin")
    _unit(portal, admin, "division", "department", "本部")
    _unit(portal, admin, "section", "department", "管理課", "division")
    _unit(portal, admin, "planning-project", "project", "計画")
    response = portal.put(
        "/api/workspace/units/division",
        headers=admin,
        json={"kind": "department", "name": "移管後名称", "parent": parent},
    )
    assert response.status_code in (409, 422) and response.json()["detail"]
    units = {item["id"]: item for item in portal.get("/api/workspace", headers=admin).json()["units"]}
    assert (units["division"]["name"], units["division"]["parent"], units["section"]["parent"]) == (
        "本部",
        "",
        "division",
    )


def test_missing_membership_target(portal):
    """所属先が既に廃止された場合は新しい所属を作らず、既存の所属を維持する。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    _unit(portal, admin, "closed-team", "project", "廃止")
    assert portal.delete("/api/workspace/units/closed-team", headers=admin).status_code == 200
    before = portal.get("/api/workspace", headers=user).json()["my_units"]
    response = portal.put(
        "/api/workspace/memberships",
        headers=admin,
        json={"subject": subject, "unit_id": "closed-team"},
    )
    assert response.status_code == 404 and response.json()["detail"]
    assert portal.get("/api/workspace", headers=user).json()["my_units"] == before


def test_department_transfer_preserves_successor_leadership(portal):
    """移管元で既に解除した所属があっても、後継部署で現在有効な役職とリーダー設定は保持される。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    for key in ("former-dept", "successor-dept"):
        _unit(portal, admin, key, "department", key)
    _assign(portal, admin, subject, "former-dept", "旧担当", False)
    _assign(portal, admin, subject, "successor-dept", "部長", True)
    removed = portal.delete(
        "/api/workspace/memberships",
        headers=admin,
        params={"subject": subject, "unit_id": "former-dept"},
    )
    assert removed.status_code == 200 and removed.json()["removed"]
    moved = portal.post(
        "/api/workspace/units/former-dept/transfer",
        headers=admin,
        json={"destination": "successor-dept"},
    )
    assert moved.status_code == 200 and moved.json()["removed"]
    usage = portal.get("/api/workspace/units/successor-dept/usage", headers=user)
    assert usage.status_code == 200
    current = [m for m in usage.json()["members"] if m["subject"] == subject and m.get("active", True)]
    assert [(m["title"], m["leader"]) for m in current] == [("部長", True)]


def test_repeated_transfer_keeps_successor_membership(portal):
    """移管済みの旧組織を再度指定しても、後継組織に引き継いだ所属を二重に移管しない。"""
    admin = headers(portal, "admin")
    user = headers(portal, "consumer")
    subject = portal.get("/api/me", headers=user).json()["subject"]
    _unit(portal, admin, "retiring", "project", "統合元")
    _unit(portal, admin, "ongoing", "project", "統合先")
    _assign(portal, admin, subject, "retiring", "担当", False)
    url = "/api/workspace/units/retiring/transfer"
    assert portal.post(url, headers=admin, json={"destination": "ongoing"}).json()["removed"]
    repeated = portal.post(url, headers=admin, json={"destination": "ongoing"})
    assert repeated.status_code in (200, 404)
    view = portal.get("/api/workspace", headers=admin).json()["memberships"]
    assert (
        len(
            [
                m
                for m in view
                if m["subject"] == subject and m["unit_id"] == "ongoing" and m.get("active", True)
            ]
        )
        == 1
    )
