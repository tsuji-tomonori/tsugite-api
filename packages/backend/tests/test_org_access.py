# 公開範囲、委任判断、個人・プロジェクト別申請、部署・役職の自動承認を確認する。
from app.core.auth import DEMO_GROUPS

from tests.support.catalog import FORM, headers, invocation_headers, publish_asset


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
    """公開範囲、委任判断、個人・プロジェクト別申請、部署・役職の自動承認を確認する"""
    admin, people = setup_people(portal, monkeypatch)
    owner = headers(portal, "provider")
    user, lead, neighbor = people["applicant"], people["approver"], people["neighbor"]
    api = portal
    key = api.post("/api/apis", headers=owner, json={**FORM, "name": "倉庫の在庫"}).json()["id"]
    url = "/api/apis/" + key
    publish_asset(api, url, owner).raise_for_status()

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
    call = invocation_headers(api, user, "field")
    assert api.get(path, headers=call).is_success and api.get(path, headers=lead).status_code == 403
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
    assert api.get(path, headers=call).status_code == 403
    assert api.get("/api/workspace/units/east/usage", headers=lead).json()["calls"] >= 4
    for endpoint in ("metrics", "access-logs", "access-logs/download", "metric-dimensions"):
        params = {"unit": "east"}
        if endpoint.startswith("access-logs"):
            params["scope"] = "audit"
        assert api.get("/api/" + endpoint, params=params, headers=neighbor).status_code == 403
        assert api.get("/api/" + endpoint, params=params, headers=lead).is_success
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
    """Cognitoグループの除外が有効で、ポータルで新設したプロジェクトへの招待も反映される"""
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
                json={
                    "full_name": "試験 花子",
                    "email": project + "@example.org",
                    "role": "provider",
                    "project": project,
                },
            )
            .raise_for_status()
            .json()["subject"]
        )
        with Session(engine()) as db:
            # A fresh JWT with no groups cannot recover a revoked Cognito-backed role.
            actor = populate(db, Actor(identity, frozenset(), frozenset(), False, False))
            assert (project in actor.owners) == (project == "new-project")
            assert (project in actor.projects) == (project == "new-project")


def test_workspace_project_visibility(portal):
    """利用者には有効な所属先だけを返し、兼務の追加と所属解除を同じセッションに反映する"""
    admin, user = (headers(portal, role) for role in ("admin", "consumer"))

    def workspace(identity):
        return portal.get("/api/workspace", headers=identity).raise_for_status().json()

    def project_ids(identity):
        return {u["id"] for u in workspace(identity)["units"] if u["kind"] == "project"}

    assert project_ids(admin) == {"finance", "supply"}
    assert project_ids(user) == {"finance"}
    assert portal.get("/api/workspace/units/supply/usage", headers=user).status_code == 403

    membership = "/api/workspace/memberships"
    portal.put(
        membership, headers=admin, json={"subject": "consumer", "unit_id": "supply"}
    ).raise_for_status()
    assert project_ids(user) == {"finance", "supply"}
    for key in ("finance", "supply"):
        portal.delete(
            membership, headers=admin, params={"subject": "consumer", "unit_id": key}
        ).raise_for_status()
    assert project_ids(user) == set()
    data = workspace(user)
    assert data["my_units"] == [] and data["memberships"] == []


def test_workspace_honors_current_groups(portal, monkeypatch):
    """招待時の所属が名簿に残っても、現在のグループから外れたプロジェクトは返さない"""
    member = (
        portal.post(
            "/api/members",
            headers=headers(portal, "admin"),
            json={
                "full_name": "試験 花子",
                "email": "former@example.org",
                "role": "consumer",
                "project": "finance",
            },
        )
        .raise_for_status()
        .json()
    )
    monkeypatch.setitem(DEMO_GROUPS, member["subject"], [])
    user = headers(portal, member["subject"])
    data = portal.get("/api/workspace", headers=user).raise_for_status().json()
    assert data["units"] == [] and data["my_units"] == [] and data["memberships"] == []


def test_workspace_department_lead_projects(portal, monkeypatch):
    """部署に所属する利用者のうち、担当リーダーだけが管理対象のプロジェクトも参照できる"""
    admin, people = setup_people(portal, monkeypatch)
    portal.delete(
        "/api/workspace/memberships", headers=admin, params={"subject": "approver", "unit_id": "field"}
    ).raise_for_status()
    for person, expected in (("approver", {"field"}), ("neighbor", set())):
        data = portal.get("/api/workspace", headers=people[person]).raise_for_status().json()
        assert {u["id"] for u in data["units"] if u["kind"] == "project"} == expected
        assert "field" not in data["my_units"]


def test_access_log_scopes(portal, monkeypatch):
    """同じ所属でも本人の履歴を分離し、配下の監査・絞り込み・出力と権限解除を検証する。"""
    import json

    from sqlalchemy.orm import Session
    from tsugite_db.models import AccessLog, Event, LogUnit
    from tsugite_db.session import engine

    admin, people = setup_people(portal, monkeypatch)
    api = portal
    # ログは呼び出した時点のプロジェクトと部署に帰属する。
    with Session(engine()) as db:
        for trace, actor, project, departments in (
            ("own", "approver", "field", ["east", "corp"]),
            ("peer", "applicant", "field", ["east", "corp"]),
            ("child", "applicant", "person-x", ["desk", "east", "corp"]),
            ("outside", "applicant", "finance", ["west", "corp"]),
        ):
            meta = dict(
                request_id=trace,
                project=project,
                actor=actor,
                owner="supply",
                asset_id="stock",
                environment="sandbox",
            )
            db.add(AccessLog(**meta, method="GET", operation="/stock", status=200, duration_ms=1))
            db.add(Event(**meta, action="invoke.end", detail="200"))
            for unit in departments:
                db.add(LogUnit(request_id=trace, unit_id=unit))
        db.commit()

    def ids(actor, **params):
        rows = api.get("/api/access-logs", headers=actor, params=params).raise_for_status().json()
        download = api.get("/api/access-logs/download", headers=actor, params=params).raise_for_status()
        found = {row["request_id"] for row in rows}
        assert {json.loads(line)["request_id"] for line in download.text.splitlines()} == found
        return found

    lead, member = people["approver"], people["applicant"]
    assert ids(lead) == {"own"}
    assert ids(admin) == set()
    assert ids(member) == {"peer", "outside", "child"}
    assert ids(lead, scope="audit") == {"own", "peer", "child"}
    assert ids(lead, scope="audit", unit="desk") == {"child"}
    assert ids(lead, scope="audit", unit="field") == {"peer", "own"}
    assert ids(admin, scope="audit") == {"own", "peer", "child", "outside"}
    assert ids(admin, scope="audit", unit="west") == {"outside"}
    for suffix in ("", "/detail", "/download", "/dimensions"):
        url = "/api/access-logs" + suffix
        for identity, params in (
            (member, {"scope": "audit"}),
            (lead, {"scope": "audit", "unit": "west"}),
            (lead, {"unit": "field"}),
        ):
            assert (
                api.get(url, headers=identity, params={**params, "request_id": "peer"}).status_code
                == 403
            )
    for identity, scope, trace, status in (
        (lead, "personal", "peer", 404),
        (lead, "audit", "peer", 200),
        (lead, "audit", "outside", 404),
        (admin, "personal", "peer", 404),
    ):
        assert (
            api.get(
                "/api/access-logs/detail", headers=identity, params={"scope": scope, "request_id": trace}
            ).status_code
            == status
        )
    assert {
        r["request_id"]
        for r in api.get("/api/audit", headers=lead).json()
        if r["action"] == "invoke.end"
    } == {"child", "own", "peer"}
    for unit in ("east", "field"):
        api.delete(
            "/api/workspace/memberships", headers=admin, params={"subject": "approver", "unit_id": unit}
        ).raise_for_status()
        if unit == "east":
            assert ids(lead, scope="audit") == {"own", "peer"}
    assert (
        api.get(
            "/api/access-logs/detail", headers=lead, params={"scope": "audit", "request_id": "peer"}
        ).status_code
        == 403
    )
    assert ids(lead) == {"own"}
