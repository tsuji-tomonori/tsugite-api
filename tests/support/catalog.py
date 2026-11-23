SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "在庫", "version": "1.0"},
    "paths": {"/items": {"get": {"responses": {"200": {"description": "在庫"}}}}},
}
FORM = {
    "owner": "supply",
    "name": "在庫",
    "summary": "棚卸しに使う",
    "targets": {"sandbox": "sample-sandbox", "production": "sample-production"},
    "spec": SPEC,
}


def headers(api, persona):
    res = api.post("/api/demo/" + persona)
    return {"Authorization": "Bearer " + res.json()["access_token"]}


def approved(api, owner, user):
    key = api.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()["id"]
    url = "/api/apis/" + key
    api.put(url + "/publication?published=true", headers=owner).raise_for_status()
    grant = {"project": "finance", "environment": "sandbox", "reason": "利用統計検証"}
    right = api.post(url + "/requests", headers=user, json=grant).raise_for_status().json()
    api.post(
        "/api/requests/" + right["id"],
        headers=owner,
        json={"action": "approve", "revision": right["revision"], "reason": "目的を確認"},
    ).raise_for_status()
    return key, url, f"/api/invoke/{key}/sandbox/finance/items"


def invocation_headers(api, user, project="finance", endpoint="/api/credentials"):
    issued = (
        api.post(
            endpoint,
            headers=user,
            json={"project": project, "name": "呼び出し試験", "kind": "personal", "mode": "bearer"},
        )
        .raise_for_status()
        .json()
    )
    return {"Authorization": "Bearer " + issued["access_token"]}
