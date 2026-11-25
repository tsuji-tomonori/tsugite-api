# メタデータの公開設定、所属の訂正、グループリーダーの閲覧範囲をAPI経由で検証する。
import pytest

from tests.support.catalog import headers


def save(portal, path, admin, data):
    response = portal.put("/api/workspace/" + path, headers=admin, json=data)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def directory_settings(portal):
    actors = {role: headers(portal, role) for role in ("admin", "consumer", "provider", "auditor")}
    admin = actors["admin"]
    save(portal, "metadata/employment-type", admin, {"label": "雇用区分", "public_values": False})
    save(portal, "metadata/job-grade", admin, {"label": "等級", "public_values": True})
    for kind, key, label, parent in (
        ("employment-type", "staff", "社員", ""),
        ("employment-type", "trainee", "研修中", "staff"),
        ("employment-type", "contractor", "契約社員", ""),
        ("job-grade", "manager-grade", "管理職", ""),
    ):
        save(portal, "units/" + key, admin, {"kind": kind, "name": label, "parent": parent})
    return actors


def test_metadata_assignments_can_be_corrected_without_adding_projects(portal, directory_settings):
    """兼務する任意属性の値を追加・訂正・解除しても既存のプロジェクトと部署の権限を保つ。"""
    admin, consumer = directory_settings["admin"], directory_settings["consumer"]
    before = portal.get("/api/me", headers=consumer).json()
    fields = {field["key"]: field for field in before["metadata_fields"]}
    assert {key for key, field in fields.items() if field["builtin"]} == {"project", "department"}
    for key in ("employment-type", "job-grade"):
        assert not fields[key]["builtin"]

    def assign(unit, title, leader=False):
        return save(
            portal,
            "memberships",
            admin,
            {
                "subject": "consumer",
                "unit_id": unit,
                "title": title,
                "leader": leader,
            },
        )

    assign("staff", "正担当")
    assign("trainee", "訓練生")
    assign("manager-grade", "副担当")
    assign("staff", "主任", leader=True)
    mine = portal.get("/api/me", headers=consumer).json()
    assert set(mine["metadata"]["employment-type"]) == {"staff", "trainee"}
    assert mine["metadata"]["job-grade"] == ["manager-grade"]
    assert mine["projects"] == before["projects"] and mine["departments"] == before["departments"]
    workspace = portal.get("/api/workspace", headers=consumer).json()
    staff = [
        m for m in workspace["memberships"] if m["subject"] == "consumer" and m["unit_id"] == "staff"
    ]
    assert len(staff) == 1 and staff[0]["title"] == "主任" and staff[0]["leader"]
    removed = portal.delete(
        "/api/workspace/memberships", headers=admin, params={"subject": "consumer", "unit_id": "staff"}
    )
    assert removed.status_code == 200
    revised = portal.get("/api/me", headers=consumer).json()
    assert revised["metadata"]["employment-type"] == ["trainee"]
    assert revised["metadata"]["job-grade"] == ["manager-grade"]
    assert "staff" not in revised["leads"]
    assert revised["projects"] == before["projects"]


def test_public_value_names_do_not_expose_rosters_and_leader_scope_stays_in_tree(
    portal, directory_settings
):
    """任意属性の名称を公開しても所属名簿を開示せず、値のリーダーは配下の名簿のみを確認できる。"""
    admin = directory_settings["admin"]
    provider = directory_settings["provider"]
    consumer = directory_settings["consumer"]
    for subject, unit, leader in (
        ("consumer", "staff", True),
        ("provider", "trainee", False),
        ("auditor", "contractor", False),
    ):
        save(
            portal,
            "memberships",
            admin,
            {"subject": subject, "unit_id": unit, "leader": leader, "title": "担当"},
        )

    def visible(auth):
        response = portal.get("/api/workspace", headers=auth)
        assert response.status_code == 200
        workspace = response.json()
        return {u["id"] for u in workspace["units"]}, {
            (m["subject"], m["unit_id"]) for m in workspace["memberships"]
        }

    private_names, _ = visible(provider)
    assert "contractor" not in private_names
    save(portal, "metadata/employment-type", admin, {"label": "契約形態", "public_values": True})
    names, roster = visible(provider)
    assert {"staff", "trainee", "contractor"} <= names
    assert ("auditor", "contractor") not in roster
    _, lead_roster = visible(consumer)
    assert ("provider", "trainee") in lead_roster
    assert ("auditor", "contractor") not in lead_roster
    updated = portal.get("/api/me", headers=consumer).json()
    field = next(field for field in updated["metadata_fields"] if field["key"] == "employment-type")
    assert field["label"] == "契約形態" and field["public_values"] and not field["builtin"]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param(
            "metadata/job-grade",
            {"label": "非管理者の更新", "public_values": True},
            marks=pytest.mark.case_detail("非管理者による項目の公開設定と表示名変更を拒否する"),
        ),
        pytest.param(
            "units/unapproved",
            {"kind": "job-grade", "name": "未承認"},
            marks=pytest.mark.case_detail("非管理者による新しい分類値の作成を拒否する"),
        ),
        pytest.param(
            "memberships",
            {"subject": "provider", "unit_id": "manager-grade", "leader": True},
            marks=pytest.mark.case_detail("非管理者による自身への分類値のリーダー付与を拒否する"),
        ),
    ],
)
def test_non_admin_cannot_change_metadata_definition_or_grant_roles(
    portal, directory_settings, path, payload
):
    """分類値の名称が公開されていても一般利用者は定義・値・所属権限を変更できない。"""
    provider = directory_settings["provider"]
    before = portal.get("/api/workspace", headers=directory_settings["admin"]).json()
    denied = portal.put("/api/workspace/" + path, headers=provider, json=payload)
    assert denied.status_code == 403
    after = portal.get("/api/workspace", headers=directory_settings["admin"]).json()
    assert after["metadata_fields"] == before["metadata_fields"]
    assert after["units"] == before["units"]
    assert after["memberships"] == before["memberships"]


def test_public_metadata_restricts_catalog_to_direct_value_members(portal, directory_settings):
    """公開名を持つ値を商品の対象にすると、下位の値だけを持つ人には見えず直接の所属変更が反映される。"""
    admin, consumer, provider = (directory_settings[key] for key in ("admin", "consumer", "provider"))
    save(portal, "memberships", admin, {"subject": "consumer", "unit_id": "trainee"})
    product = portal.post(
        "/api/apis",
        headers=provider,
        json={
            "owner": "supply",
            "name": "雇用区分限定商品",
            "slug": "staff-inventory",
            "summary": "社員の在庫照会",
            "targets": {"sandbox": "sample-sandbox"},
            "spec": {
                "openapi": "3.0.3",
                "info": {"title": "社員の在庫", "version": "1.0"},
                "paths": {"/items": {"get": {"responses": {"200": {"description": "在庫"}}}}},
            },
        },
    )
    assert product.status_code == 201, product.text
    key = product.json()["id"]
    path = f"/api/apis/{key}"
    policy = {"visibility": "restricted", "metadata_values": ["staff"]}
    hidden_choice = portal.put(
        path + "/policy", headers=provider, params={"revision": product.json()["revision"]}, json=policy
    )
    assert hidden_choice.status_code == 422, hidden_choice.text
    save(portal, "metadata/employment-type", admin, {"label": "雇用区分", "public_values": True})
    accepted = portal.put(
        path + "/policy", headers=provider, params={"revision": product.json()["revision"]}, json=policy
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["metadata_values"] == ["staff"]
    published = portal.put(path + "/publication", headers=provider, params={"published": True})
    assert published.status_code == 200

    def catalog():
        response = portal.get("/api/apis", headers=consumer)
        assert response.status_code == 200
        return {listing["id"] for listing in response.json()}

    assert key not in catalog()
    save(portal, "memberships", admin, {"subject": "consumer", "unit_id": "staff"})
    assert key in catalog()
    portal.delete(
        "/api/workspace/memberships", headers=admin, params={"subject": "consumer", "unit_id": "staff"}
    ).raise_for_status()
    assert key not in catalog()


def test_metadata_hierarchy_cannot_move_members_into_a_different_attribute(portal, directory_settings):
    """別項目の値への移管を拒否し、元項目の所属・役割とプロジェクト権限を維持する。"""
    admin, consumer = directory_settings["admin"], directory_settings["consumer"]
    save(
        portal,
        "memberships",
        admin,
        {"subject": "consumer", "unit_id": "staff", "title": "社員代表", "leader": True},
    )
    before = portal.get("/api/me", headers=consumer).json()
    denied = portal.post(
        "/api/workspace/units/staff/transfer", headers=admin, json={"destination": "manager-grade"}
    )
    assert 400 <= denied.status_code < 500
    after = portal.get("/api/me", headers=consumer).json()
    assert after["metadata"] == before["metadata"] and after["projects"] == before["projects"]
    workspace = portal.get("/api/workspace", headers=consumer).json()
    membership = next(
        m for m in workspace["memberships"] if m["subject"] == "consumer" and m["unit_id"] == "staff"
    )
    assert membership["title"] == "社員代表" and membership["leader"]


def test_invalid_attribute_hierarchy_leaves_existing_values_and_roles_intact(portal, directory_settings):
    """未定義の項目、他項目の親、循環する親を拒否し、既存の分類値と所属を維持する。"""
    admin = directory_settings["admin"]
    save(portal, "memberships", admin, {"subject": "consumer", "unit_id": "trainee", "title": "研修生"})
    before = portal.get("/api/workspace", headers=admin).json()
    for key, kind, parent in (
        ("undeclared-value", "unregistered-field", ""),
        ("invalid-child", "job-grade", "staff"),
        ("staff", "employment-type", "trainee"),
    ):
        result = portal.put(
            "/api/workspace/units/" + key,
            headers=admin,
            json={"kind": kind, "name": "無効な移動", "parent": parent},
        )
        assert 400 <= result.status_code < 500, result.text
    after = portal.get("/api/workspace", headers=admin).json()
    assert after["units"] == before["units"]
    assert after["memberships"] == before["memberships"]


def test_value_in_use_must_be_released_before_removal(portal, directory_settings):
    """利用者が所属する分類値の削除を拒否し、所属を解除した後はその値だけを削除できる。"""
    admin, consumer = directory_settings["admin"], directory_settings["consumer"]
    save(portal, "memberships", admin, {"subject": "consumer", "unit_id": "manager-grade"})
    url = "/api/workspace/units/manager-grade"
    blocked = portal.delete(url, headers=admin)
    assert blocked.status_code == 409, blocked.text
    mine = portal.get("/api/me", headers=consumer).json()
    assert mine["metadata"]["job-grade"] == ["manager-grade"]
    released = portal.delete(
        "/api/workspace/memberships",
        headers=admin,
        params={"subject": "consumer", "unit_id": "manager-grade"},
    )
    assert released.status_code == 200
    assert portal.delete(url, headers=admin).status_code == 200
    snapshot = portal.get("/api/workspace", headers=admin).json()
    assert "manager-grade" not in {value["id"] for value in snapshot["units"]}
    assert "job-grade" in {field["key"] for field in snapshot["metadata_fields"]}


@pytest.mark.parametrize(
    ("key", "label"),
    [
        pytest.param(
            "JobRole",
            "役割",
            marks=pytest.mark.case_detail("公開契約の形式に合わない項目キーを拒否する"),
        ),
        pytest.param("a" * 64, "役割", marks=pytest.mark.case_detail("63文字を超えるキーを拒否する")),
        pytest.param("job-role", "", marks=pytest.mark.case_detail("空の表示名で属性を作成しない")),
        pytest.param(
            "job-role", "役" * 121, marks=pytest.mark.case_detail("120文字を超える表示名を拒否する")
        ),
    ],
)
def test_invalid_metadata_keys_and_labels_are_not_registered(portal, key, label):
    """属性のキーや表示名が公開された制約の範囲外なら入力エラーとなり項目一覧に追加しない。"""
    admin = headers(portal, "admin")
    response = portal.put("/api/workspace/metadata/" + key, headers=admin, json={"label": label})
    assert response.status_code == 422
    assert key not in {
        field["key"] for field in portal.get("/api/workspace", headers=admin).json()["metadata_fields"]
    }


def test_attribute_value_identity_survives_rename_and_cannot_be_retyped(portal, directory_settings):
    """利用中の値の名称を訂正しても識別子と所属を維持し、別項目への付け替えを拒否する。"""
    admin, consumer = directory_settings["admin"], directory_settings["consumer"]
    save(
        portal,
        "memberships",
        admin,
        {"subject": "consumer", "unit_id": "contractor", "title": "委託先責任者"},
    )
    save(portal, "units/contractor", admin, {"kind": "employment-type", "name": "業務委託"})
    invalid = portal.put(
        "/api/workspace/units/contractor", headers=admin, json={"kind": "job-grade", "name": "業務委託"}
    )
    assert 400 <= invalid.status_code < 500, invalid.text
    mine = portal.get("/api/me", headers=consumer).json()
    assert mine["metadata"]["employment-type"] == ["contractor"]
    assert "contractor" not in mine["metadata"].get("job-grade", [])
    workspace = portal.get("/api/workspace", headers=consumer).json()
    unit = next(value for value in workspace["units"] if value["id"] == "contractor")
    assert unit["kind"] == "employment-type" and unit["name"] == "業務委託"
