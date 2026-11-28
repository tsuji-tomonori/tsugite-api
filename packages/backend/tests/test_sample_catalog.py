# カタログでサンプル商品を検索・取得できることを検証する。
from packages.tools.demo.seed_marketplace import CATALOG, offer, seed
from tests.support.catalog import SPEC, headers, invocation_headers


def test_seed_replaces_old_contract_and_calls_product(portal):
    """旧版の出品を同じIDで更新し、再実行後も承認済みの商品がSQLiteの配送状況を返す。"""
    owner = headers(portal, "provider")
    user = headers(portal, "consumer")
    parcel = next(product for product in CATALOG if product["slug"] == "parcel-tracking")
    listing = offer(parcel, 1)
    old = {**listing, "base_path": "", "spec": SPEC}
    key = portal.post("/api/apis", headers=owner, json=old).raise_for_status().json()["id"]
    portal.put(f"/api/apis/{key}/publication?published=true", headers=owner).raise_for_status()
    portal.base_url = "http://testserver/api/"
    ids = seed(portal, 1)
    assert len(set(ids)) == 12 and key in ids
    detail = portal.get(f"apis/{key}", headers=owner).raise_for_status().json()
    assert detail["spec"] == listing["spec"] and detail["published"]
    grant = (
        portal.post(
            f"apis/{key}/requests",
            headers=user,
            json={"project": "finance", "environment": "sandbox", "reason": "配送確認"},
        )
        .raise_for_status()
        .json()
    )
    portal.post(
        "requests/" + grant["id"],
        headers=owner,
        json={"action": "approve", "revision": grant["revision"], "reason": "用途確認"},
    ).raise_for_status()
    assert seed(portal, 1) == ids
    auth = invocation_headers(portal, user, endpoint="credentials")
    result = portal.get(f"invoke/{listing['slug']}/sandbox/finance/parcels/JP17", headers=auth)
    assert result.raise_for_status().json() == {
        "parcel": "JP17",
        "status": "配送中",
        "weight_grams": 750,
    }
