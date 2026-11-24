from copy import deepcopy

from packages.backend.tests.test_org_access import setup_people
from tests.support.catalog import FORM, headers, invocation_headers


def test_three_environments_and_ordered_reviews(portal, monkeypatch):
    """環境別の承認条件を守り、複数の承認を指定の順序で行う"""
    _, people = setup_people(portal, monkeypatch)
    owner = headers(portal, "provider")
    applicant, lead = people["applicant"], people["approver"]
    form = {
        **FORM,
        "targets": {**FORM["targets"], "staging": "sample-staging"},
        "offers": {
            "sandbox": {"route": "auto"},
            "staging": {"route": "provider"},
            "production": {
                "instructions": "検証結果を申請してください",
                "route": "custom",
                "steps": ["department", "unit/east", "provider"],
                "terms": "利用規約1版",
                "fields": [{"label": "試験ID", "allowed_values": ["QA-330"]}],
            },
        },
    }
    asset = portal.post("/api/apis", headers=owner, json=form).raise_for_status().json()["id"]
    url = "/api/apis/" + asset
    portal.put(url + "/publication?published=true", headers=owner).raise_for_status()
    detail = portal.get(url, headers=applicant).raise_for_status()
    assert "QA-330" not in detail.text
    data = {
        "environment": "production",
        "project": "field",
        "reason": "本番切替",
        "terms_accepted": True,
        "answers": {"試験ID": "QA-330"},
        "offer_version": detail.json()["offers"]["production"]["version"],
    }

    def submit(**changes):
        return portal.post(url + "/requests", headers=applicant, json={**data, **changes})

    assert submit(offer_version="outdated").status_code == 409
    for invalid in ({"terms_accepted": False}, {"answers": {}}, {"answers": {"試験ID": "unknown"}}):
        assert submit(**invalid).status_code == 422
    base = submit(environment="sandbox", answers={}, offer_version="").raise_for_status().json()
    assert base["status"] == "approved"
    row = submit().raise_for_status().json()

    def decide(actor, revision):
        return portal.post(
            "/api/requests/" + row["id"],
            headers=actor,
            json={"revision": revision, "reason": "確認済み", "action": "approve"},
        )

    call = invocation_headers(portal, applicant, "field")
    path = f"/api/invoke/{asset}/production/field/items"
    assert row["stage"] == "department" and row["status"] == "pending"
    assert decide(owner, row["revision"]).status_code == 403
    assert decide(people["neighbor"], row["revision"]).status_code == 403
    assert not any(
        r["id"] == row["id"] for r in portal.get("/api/requests?incoming=true", headers=owner).json()
    )
    for expected in ("unit/east", "provider"):
        assert portal.get(path, headers=call).status_code == 403
        row = decide(lead, row["revision"]).raise_for_status().json()
        assert row["stage"] == expected and row["status"] == "pending"
    assert decide(lead, row["revision"]).status_code == 403
    assert portal.get(path, headers=call).status_code == 403
    approved = decide(owner, row["revision"]).raise_for_status().json()
    assert approved["status"] == "approved" and len(approved["application"]["decisions"]) == 3
    assert portal.get(path, headers=call).status_code == 200
    assert portal.get(path.replace("production", "staging"), headers=call).status_code == 403
    form["offers"]["production"]["terms"] = "利用規約2版"
    portal.put(
        url, params={"revision": detail.json()["revision"]}, headers=owner, json=form
    ).raise_for_status()
    assert portal.get(path, headers=call).status_code == 403
    assert portal.get(path.replace("production", "sandbox"), headers=call).status_code == 200


def test_publication_history_and_archive_failures(portal, monkeypatch):
    """公開仕様の履歴を保持し、保管に失敗した公開を確定しない"""
    from app.integrations import spec_archive
    from botocore.exceptions import ClientError

    owner = headers(portal, "provider")
    monkeypatch.setenv("SPEC_BUCKET", "private-test")
    objects = {}

    class Archive:
        failing = True

        def put_object(self, *, Bucket, Key, Body, IfNoneMatch, ContentType):
            assert Bucket == "private-test" and IfNoneMatch == "*" and ContentType == "application/json"
            if self.failing or Key in objects:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied" if self.failing else "PreconditionFailed"}},
                    "PutObject",
                )
            objects[Key] = Body

    archive = Archive()
    monkeypatch.setattr(spec_archive.boto3, "client", lambda name: archive)
    assert portal.post("/api/apis", headers=owner, json=FORM).status_code == 503
    assert portal.get("/api/apis?inventory=true", headers=owner).json() == []
    archive.failing = False
    result = portal.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()
    url = "/api/apis/" + result["id"]
    first = portal.put(url + "/publication?published=true", headers=owner).raise_for_status().json()
    updated = deepcopy(FORM)
    updated["spec"]["info"]["version"] = "2.0"
    updated["spec"]["openapi"] = "3.1.0"
    updated["spec"]["paths"]["/items"]["get"]["summary"] = "倉庫別在庫"
    updated["spec"]["paths"]["/health"] = deepcopy(updated["spec"]["paths"]["/items"])
    portal.put(
        url,
        params={"revision": first["revision"]},
        json={**updated, "release_note": "稼働確認を追加"},
        headers=owner,
    ).raise_for_status()
    archive.failing = True
    assert portal.put(url + "/publication?published=true", headers=owner).status_code == 503
    assert not portal.get(url, headers=owner).json()["published"]
    archive.failing = False
    for _ in range(2):
        portal.put(url + "/publication?published=true", headers=owner).raise_for_status()
    latest, initial = portal.get(url, headers=owner).json()["releases"]
    assert (latest["api_version"], latest["openapi"], latest["added"], latest["changed"]) == (
        "2.0",
        "3.1.0",
        ["GET /health"],
        ["GET /items"],
    )
    assert initial["number"] == 1 and latest["note"] == "稼働確認を追加" and len(objects) == 2


def test_internal_path_item_reference_is_invokable(portal):
    """同じ内部参照を使う複数のOpenAPIパスで操作を解決できる"""
    from app.apis.gateway import operation_template
    from app.core.releases import entries

    spec = deepcopy(FORM["spec"])
    spec.update(openapi="3.1.0", components={"pathItems": {"Stock": spec["paths"]["/items"]}})
    spec["paths"] = {
        "/one": {"$ref": "#/components/pathItems/Stock"},
        "/two": {"$ref": "#/components/pathItems/Stock"},
    }
    assert operation_template(spec, "GET", "/two") == "/two"
    assert {"GET /one", "GET /two"} <= entries(spec).keys()
