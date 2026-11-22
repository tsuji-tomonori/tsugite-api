"""Example upstream for the operations in docs/examples/stock.openapi.json."""

import json


def handler(event, context):
    item = {"sku": "TS-01", "stock": 12}
    path = event.get("rawPath", "")
    status = 200
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
