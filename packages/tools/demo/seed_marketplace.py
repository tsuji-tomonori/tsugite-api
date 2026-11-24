# サンプル商品を登録して公開する。
"""Publish example listings using the local portal's provider flow."""

import argparse
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
CATALOG = json.loads((ROOT / "docs/examples/marketplace.json").read_text(encoding="utf-8"))


def offer(product, edition=None):
    name = product["name"]
    if edition:
        areas = (
            "札幌",
            "旭川",
            "仙台",
            "新潟",
            "金沢",
            "東京",
            "横浜",
            "静岡",
            "浜松",
            "名古屋",
            "京都",
            "大阪",
            "神戸",
            "岡山",
            "広島",
            "松山",
            "福岡",
            "熊本",
            "那覇",
            "岐阜",
        )
        region = areas[(edition - 1) % len(areas)]
        office = (edition - 1) // len(areas) + 1
        name = f"{region}{office if office > 1 else ''}｜{name}"
    env = product["environment"]
    slug = product["slug"] + (f"-{edition}" if edition else "")
    return {
        "name": name,
        "slug": slug,
        "owner": "supply",
        "summary": product["summary"],
        "targets": {env: "sample-" + env},
        "spec": {
            "openapi": "3.0.3",
            "info": {"title": name, "version": "1.0.0"},
            "paths": {
                product["path"]: {
                    product["method"].lower(): {
                        "summary": product["summary"],
                        "responses": {"200": {"description": "処理結果"}},
                    }
                }
            },
        },
    }


def seed(api, editions):
    login = api.post("demo/provider")
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    inventory = api.get("apis", params={"inventory": True}, headers=headers)
    inventory.raise_for_status()
    existing = {row["name"]: row for row in inventory.json()}
    ids = []
    for edition in range(1, editions + 1):
        for product in CATALOG:
            data = offer(product, edition)
            row = existing.get(data["name"])
            if row is None:
                result = api.post("apis", headers=headers, json=data)
                result.raise_for_status()
                row = result.json()
            if not row["published"]:
                response = api.put(
                    f"apis/{row['id']}/publication", params={"published": True}, headers=headers
                )
                response.raise_for_status()
            ids.append(row["id"])
    return ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ローカルデモのカタログに用途の異なる6種類のAPIを公開します"
    )
    parser.add_argument("--editions", type=int, default=1, choices=range(1, 101), metavar="1..100")
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8000/api/", trust_env=False) as client:
        print(f"{len(seed(client, args.editions))} 件を公開しました。")
