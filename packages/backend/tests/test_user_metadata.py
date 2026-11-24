from tests.support.catalog import FORM, headers


def test_metadata_groups_and_visibility(portal):
    """任意属性は所属単位で閲覧でき、グループのリーダーや役職を業務権限に引き継がない。"""
    admin, user, other = (headers(portal, p) for p in ("admin", "consumer", "provider"))
    field = "/api/workspace/metadata/company"
    values = "/api/workspace/units/"
    assign = "/api/workspace/memberships"
    definition = {"label": "所属会社"}
    assert portal.put(field, headers=user, json=definition).status_code == 403
    assert (
        portal.put("/api/workspace/metadata/project", headers=admin, json=definition).status_code == 409
    )
    assert (
        portal.put(values + "acme", headers=admin, json={"name": "A社", "kind": "company"}).status_code
        == 422
    )
    portal.put(field, headers=admin, json=definition).raise_for_status()
    for key, parent in [("acme", ""), ("acme-sub", "acme"), ("another", "")]:
        portal.put(
            values + key, headers=admin, json={"kind": "company", "name": key, "parent": parent}
        ).raise_for_status()
    assert (
        portal.put(
            values + "acme", headers=admin, json={"kind": "company", "name": "A社", "parent": "acme-sub"}
        ).status_code
        == 422
    )
    assert (
        portal.put(
            values + "p", headers=admin, json={"kind": "project", "name": "p", "parent": "acme"}
        ).status_code
        == 422
    )
    for subject, key, lead in [("consumer", "acme", True), ("provider", "acme-sub", False)]:
        portal.put(
            assign,
            headers=admin,
            json={"subject": subject, "unit_id": key, "leader": lead, "title": "主任"},
        ).raise_for_status()
    me = portal.get("/api/me", headers=user).json()
    assert me["metadata"] == {"company": ["acme"], "project": ["finance"]}
    assert me["projects"] == ["finance"] and not me["titles"] and not me["leads"]
    workspace = portal.get("/api/workspace", headers=user).json()
    assert {r["subject"] for r in workspace["memberships"] if r["unit_id"] == "acme-sub"} == {"provider"}
    assert not any(u["id"] == "another" for u in workspace["units"])
    assert not workspace["leads"]
    assert portal.get(values + "acme/usage", headers=user).status_code == 403
    assert portal.get("/api/access-logs?scope=audit", headers=user).status_code == 403
    peer_view = portal.get("/api/workspace", headers=other).json()
    assert all(r["subject"] != "consumer" for r in peer_view["memberships"])
    portal.put(field, headers=admin, json={"label": "会社", "public_values": True}).raise_for_status()
    peer_view = portal.get("/api/workspace", headers=other).json()
    assert any(u["id"] == "another" for u in peer_view["units"])
    assert all(r["subject"] != "consumer" for r in peer_view["memberships"])
    portal.delete(
        assign, headers=admin, params={"subject": "consumer", "unit_id": "acme"}
    ).raise_for_status()
    assert portal.get("/api/me", headers=user).json()["metadata"] == {"project": ["finance"]}


def test_metadata_audience_and_transfer(portal):
    """限定公開の任意属性条件を移管時に引き継ぎ、所属を解除すると閲覧できなくなる。"""
    admin, owner, user = (headers(portal, p) for p in ("admin", "provider", "consumer"))
    field = "/api/workspace/metadata/employment"
    portal.put(
        field, headers=admin, json={"label": "雇用区分", "public_values": True}
    ).raise_for_status()
    values = "/api/workspace/units/"
    for key in ["staff", "permanent"]:
        portal.put(
            values + key, headers=admin, json={"kind": "employment", "name": key}
        ).raise_for_status()
    asset = (
        "/api/apis/" + portal.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()["id"]
    )
    portal.put(asset + "/publication?published=true", headers=owner).raise_for_status()

    def policy(data):
        revision = portal.get(asset, headers=owner).json()["revision"]
        return portal.put(asset + "/policy", params={"revision": revision}, headers=owner, json=data)

    assert policy({"metadata_values": ["missing"]}).status_code == 422
    policy({"visibility": "restricted", "metadata_values": ["staff"]}).raise_for_status()
    # 従来のクライアントが既存の項目だけを送信しても属性条件を維持する。
    policy({"visibility": "restricted"}).raise_for_status()
    assert portal.get(asset, headers=user).status_code == 404
    assign = "/api/workspace/memberships"
    portal.put(
        assign, headers=admin, json={"subject": "consumer", "unit_id": "staff"}
    ).raise_for_status()
    assert portal.get(asset, headers=user).status_code == 200
    portal.post(
        values + "staff/transfer", headers=admin, json={"destination": "permanent"}
    ).raise_for_status()
    assert portal.get(asset + "/policy", headers=owner).json()["metadata_values"] == ["permanent"]
    assert portal.get(asset, headers=user).status_code == 200
    portal.delete(
        assign, headers=admin, params={"subject": "consumer", "unit_id": "permanent"}
    ).raise_for_status()
    assert portal.get(asset, headers=user).status_code == 404
