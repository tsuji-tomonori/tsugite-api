"""商品の提供者が購読者の操作権限を設定し、解除できることを確認する。"""

from tests.support.catalog import approved, headers


def test_subscriber_operation_policy_is_scoped_and_resettable(portal):
    """提供者は購読者に仕様内の操作を設定でき、解除すると個別設定が一覧から消える。"""
    owner, user = (headers(portal, name) for name in ("provider", "consumer"))
    _, product, _ = approved(portal, owner, user)
    url = product + "/operation-policy"
    policy = portal.get(url, headers=owner).raise_for_status().json()
    assert policy["operations"] == ["GET /items"] and policy["permissions"] == {}
    subject = portal.get("/api/me", headers=user).raise_for_status().json()["subject"]
    assert subject in {entry["subject"] for entry in policy["members"]}
    assert portal.get(url, headers=user).status_code == 403

    def save(who, operations):
        return portal.put(url, headers=owner, json={"subject": who, "operations": operations})

    assert save(subject, ["DELETE /undefined"]).status_code == 422
    assert save("missing", []).status_code == 422
    for ops in (["GET /items"], [], None):
        assert save(subject, ops).raise_for_status().json() == {"subject": subject, "operations": ops}
        saved = portal.get(url, headers=owner).raise_for_status().json()["permissions"]
        assert saved == ({} if ops is None else {subject: ops})
