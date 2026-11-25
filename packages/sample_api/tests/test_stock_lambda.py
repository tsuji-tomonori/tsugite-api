import json

import pytest
from sample_api.main import handler


@pytest.mark.parametrize(
    ("path", "status", "body"),
    [
        pytest.param(
            "/items",
            200,
            {"items": [{"sku": "TS-01", "stock": 12}]},
            id="list",
            marks=pytest.mark.case_detail("登録されている商品の在庫一覧を返す"),
        ),
        pytest.param(
            "/items/TS-01",
            200,
            {"sku": "TS-01", "stock": 12},
            id="detail",
            marks=pytest.mark.case_detail("指定した商品の在庫を返す"),
        ),
        pytest.param(
            "/items/UNKNOWN",
            404,
            {"message": "商品が見つかりません"},
            id="missing",
            marks=pytest.mark.case_detail("未登録の商品は該当なしと返す"),
        ),
    ],
)
@pytest.mark.usefixtures("lambda_event_loop")
def test_stock_response(path: str, status: int, body: dict[str, object]) -> None:
    """在庫サンプルが操作に応じたステータスとJSON応答を返す。"""
    result = handler(
        {
            "version": "2.0",
            "rawPath": path,
            "requestContext": {"http": {"method": "GET", "path": path, "sourceIp": "127.0.0.1"}},
            "headers": {},
        },
        None,
    )
    assert result["statusCode"] == status
    assert result["headers"]["content-type"] == "application/json"
    assert json.loads(result["body"]) == body
