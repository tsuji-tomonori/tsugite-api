from app.core.auth import DEMO_GROUPS

from tests.support.catalog import FORM, headers


def setup_people(api, monkeypatch):
    for name in ("applicant", "approver", "neighbor", "title-user"):
        monkeypatch.setitem(DEMO_GROUPS, name, [])
    admin = headers(api, "admin")
    for key, kind, parent in (
        ("corp", "department", ""),
        ("east", "department", "corp"),
        ("desk", "department", "east"),
        ("west", "department", "corp"),
        ("field", "project", "east"),
    ):
        api.put(
            "/api/workspace/units/" + key,
            headers=admin,
            json={"kind": kind, "parent": parent, "name": key},
        ).raise_for_status()
    for name, dept, title, lead in (
        ("applicant", "desk", "担当", False),
        ("applicant", "west", "兼務", False),
        ("approver", "east", "係長", True),
        ("title-user", "west", "主査", False),
        ("neighbor", "corp", "", False),
        ("applicant", "field", "", False),
        ("approver", "field", "", True),
    ):
        api.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"unit_id": dept, "subject": name, "title": title, "leader": lead},
        ).raise_for_status()
    return admin, {n: headers(api, n) for n in ("applicant", "approver", "neighbor", "title-user")}


def test_delegation_search_and_personal_isolation(portal, monkeypatch):
    admin, people = setup_people(portal, monkeypatch)
    owner = headers(portal, "provider")
    user, lead, neighbor = people["applicant"], people["approver"], people["neighbor"]
    api = portal
    key = api.post("/api/apis", headers=owner, json={**FORM, "name": "倉庫の在庫"}).json()["id"]
    url = "/api/apis/" + key
    api.put(url + "/publication?published=true", headers=owner).raise_for_status()

    def policy(**data):
        rev = api.get(url, headers=owner).json()["revision"]
        return api.put(
            url + "/policy", headers=owner, params={"revision": rev}, json=data
        ).raise_for_status()

    policy(visibility="restricted", departments=["east"], delegates=["east"])
    for search in ("/api/apis?q=inventory", "/api/catalog-page?q=inventory"):
        hidden = api.get(search, headers=neighbor).json()
        assert (hidden if isinstance(hidden, list) else hidden["items"]) == []
        visible = api.get(search, headers=user).json()
        assert [r["id"] for r in (visible if isinstance(visible, list) else visible["items"])] == [key]
    assert api.get(url, headers=neighbor).status_code == 404
    data = {"project": "field", "environment": "sandbox", "reason": "個人で使用", "personal": True}
    own = api.post(url + "/requests", json=data, headers=user).raise_for_status().json()
    assert own["status"] == "pending" and own["subject"] == "applicant"
    assert [r["id"] for r in api.get("/api/requests?incoming=true", headers=lead).json()] == [own["id"]]
    assert api.get("/api/requests?incoming=true", headers=neighbor).json() == []
    decision = {"revision": own["revision"], "action": "approve", "reason": "委任先で確認"}
    assert api.post("/api/requests/" + own["id"], json=decision, headers=neighbor).status_code == 403
    api.post("/api/requests/" + own["id"], json=decision, headers=lead).raise_for_status()
    path = f"/api/invoke/{key}/sandbox/field/items"
    assert api.get(path, headers=user).is_success and api.get(path, headers=lead).status_code == 403
    shared = api.post(
        "/api/keys",
        headers=user,
        json={"kind": "shared", "project": "field", "name": "共有", "api_ids": []},
    ).json()
    assert api.get(path, headers={"Authorization": "Bearer " + shared["secret"]}).status_code == 403
    assert api.get(path, headers={**user, "X-Tsugite-Key-Id": shared["id"]}).status_code == 403
    policy(visibility="restricted", departments=["east"], auto_departments=["east"])
    org = (
        api.post(url + "/requests", json={**data, "personal": False}, headers=user)
        .raise_for_status()
        .json()
    )
    assert org["status"] == "approved" and org["id"] != own["id"]
    assert api.get(path, headers={"Authorization": "Bearer " + shared["secret"]}).is_success
    assert (
        api.put("/api/workspace/units/east/state", json={"stopped": True}, headers=neighbor).status_code
        == 403
    )
    api.put("/api/workspace/units/east/state", json={"stopped": True}, headers=lead).raise_for_status()
    assert api.get(path, headers={"Authorization": "Bearer " + shared["secret"]}).status_code == 403
    assert api.get(path, headers=user).status_code == 403
    assert api.get("/api/workspace/units/east/usage", headers=lead).json()["calls"] >= 4
    for endpoint in ("metrics", "access-logs", "access-logs/download", "metric-dimensions"):
        assert api.get("/api/" + endpoint + "?unit=east", headers=neighbor).status_code == 403
        assert api.get("/api/" + endpoint + "?unit=east", headers=lead).is_success
    assert (
        sum(b["calls"] for b in api.get("/api/metrics?unit=east", headers=lead).json()["points"])
        == api.get("/api/workspace/units/east/usage", headers=lead).json()["calls"]
    )
    assert api.get("/api/workspace/units/west/usage", headers=lead).status_code == 403
    assert (
        api.put(
            "/api/workspace/units/corp",
            json={"kind": "department", "name": "本部", "parent": "desk"},
            headers=admin,
        ).status_code
        == 422
    )
    assert api.put("/api/workspace/units/east/state", json={"stopped": False}, headers=lead).is_success
    policy(visibility="all", auto_titles=["主査"])
    individual = people["title-user"]
    personal = api.get("/api/me", headers=individual).json()["personal_project"]
    approved = (
        api.post(url + "/requests", headers=individual, json={**data, "project": personal})
        .raise_for_status()
        .json()
    )
    assert approved["status"] == "approved"
    private_key = (
        api.post(
            "/api/keys",
            headers=individual,
            json={"kind": "personal", "name": "個人", "project": personal, "api_ids": [key]},
        )
        .raise_for_status()
        .json()
    )
    assert api.get(
        path.replace("field", personal), headers={**individual, "X-API-Key": private_key["secret"]}
    ).is_success
    assert (
        api.get(
            path.replace("field", personal), headers={**user, "X-API-Key": private_key["secret"]}
        ).status_code
        == 403
    )
    assert (
        api.get(
            path.replace("field", personal), headers={"Authorization": "Bearer " + private_key["secret"]}
        ).status_code
        == 403
    )
    api.delete(
        "/api/workspace/memberships", params={"subject": "approver", "unit_id": "east"}, headers=admin
    ).raise_for_status()
    assert api.get("/api/workspace/units/east/usage", headers=lead).status_code == 403


def test_invitation_respects_identity_source(portal):
    from app.core.auth import Actor
    from app.core.workspace import populate
    from sqlalchemy.orm import Session
    from tsugite_db.session import engine

    admin = headers(portal, "admin")
    portal.put(
        "/api/workspace/units/new-project", json={"kind": "project", "name": "企画案件"}, headers=admin
    ).raise_for_status()
    for project in ("finance", "new-project"):
        identity = (
            portal.post(
                "/api/members",
                headers=admin,
                json={"email": project + "@example.org", "role": "provider", "project": project},
            )
            .raise_for_status()
            .json()["subject"]
        )
        with Session(engine()) as db:
            # A fresh JWT with no groups cannot recover a revoked Cognito-backed role.
            actor = populate(db, Actor(identity, frozenset(), frozenset(), False, False))
            assert (project in actor.owners) == (project == "new-project")
            assert (project in actor.projects) == (project == "new-project")
