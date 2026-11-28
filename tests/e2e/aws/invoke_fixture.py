"""RustPythonでLambda転送経路を検査するための固定応答。商品本体はCPythonで検査する。"""

import json


def handler(event, context):
    item = {"sku": "TS-01", "stock": 12}
    responses = {"/items": {"items": [item]}, "/items/TS-01": item}
    path = event["rawPath"]
    return {
        "statusCode": 200 if path in responses else 404,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(responses.get(path, {"message": "商品が見つかりません"})),
    }
