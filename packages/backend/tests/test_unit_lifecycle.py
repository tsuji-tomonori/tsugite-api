from tests.support.catalog import approved, headers, invocation_headers


def test_unit_retirement(portal):
    """管理者だけが空の部署を子から削除でき、廃止した識別子は再作成できない。"""
    admin, user = (headers(portal, role) for role in ("admin", "consumer"))
    path = "/api/workspace/units/"
    for key, parent in (("xx", ""), ("xx-ka", "xx")):
        portal.put(
            path + key, headers=admin, json={"kind": "department", "name": key, "parent": parent}
        ).raise_for_status()
    assert portal.delete(path + "xx-ka", headers=user).status_code == 403
    assert portal.delete(path + "xx", headers=admin).status_code == 409
    for key in ("xx-ka", "xx", "xx"):
        portal.delete(path + key, headers=admin).raise_for_status()
    assert (
        portal.put(path + "xx", headers=admin, json={"kind": "department", "name": "別部署"}).status_code
        == 409
    )
    assert portal.delete(path + "finance", headers=admin).status_code == 409
    assert portal.delete(path + "unknown", headers=admin).status_code == 404


def test_project_transfer(portal):
    """提供・利用を既存プロジェクトへ移管し、公開状態・旧URLと新URLでの認証済み呼び出しを確認する。"""
    admin, owner, user = (headers(portal, role) for role in ("admin", "provider", "consumer"))
    key, url, old_path = approved(portal, owner, user)
    path = "/api/workspace/units/"
    for dst in ("stores", "delivery"):
        portal.put(path + dst, headers=admin, json={"kind": "project", "name": dst}).raise_for_status()
    for src, dst in (("supply", "stores"), ("finance", "delivery")):
        portal.post(
            path + src + "/transfer", headers=admin, json={"destination": dst}
        ).raise_for_status()
        portal.post(
            path + src + "/transfer", headers=admin, json={"destination": dst}
        ).raise_for_status()
    listing = portal.get(url, headers=owner).raise_for_status().json()
    assert listing["owner"] == "stores" and listing["published"]
    assert portal.get("/api/me", headers=user).json()["projects"] == ["delivery"]
    assert portal.get("/api/me", headers=owner).json()["targets"]["sample-sandbox"]["owner"] == "stores"
    token = invocation_headers(portal, user, project="delivery")
    for route in (old_path, old_path.replace("/finance/", "/delivery/")):
        portal.get(route, headers=token).raise_for_status()
    tree = portal.get("/api/workspace", headers=admin).json()["units"]
    assert {row["id"] for row in tree} == {"stores", "delivery"}
