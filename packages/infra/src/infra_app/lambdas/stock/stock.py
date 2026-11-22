"""在庫サンプルの一覧照会・商品別照会を処理するLambda。"""

import json
from typing import TypedDict


class StockEvent(TypedDict, total=False):
    rawPath: str


class StockResponse(TypedDict):
    statusCode: int
    headers: dict[str, str]
    body: str


def handler(event: StockEvent, context: object) -> StockResponse:
    item: dict[str, object] = {"sku": "TS-01", "stock": 12}
    path = event.get("rawPath", "")
    status = 200
    result: dict[str, object]
    if "/items/" in path:
        if path.rsplit("/", 1)[-1] == item["sku"]:
            result = item
        else:
            status, result = 404, {"message": "商品が見つかりません"}
    else:
        result = {"items": [item]}
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(result),
    }
