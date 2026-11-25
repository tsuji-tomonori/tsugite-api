# 操作別の未検証ステータスを検出する。
from packages.tools.testing.http_contracts import missing_responses


def test_missing_status_is_scoped_to_the_operation():
    """別の操作で同じ500を観測しても、未検証の操作とステータスを報告する。"""
    operations = {"get": {"responses": {"200": {}, "500": {}}}}
    document = {"paths": {"/a": operations, "/b": operations}}
    report = {
        "endpoints": [
            {"path": "/a", "methods": [{"method": "GET", "response_codes": {"200": 1, "500": 1}}]},
            {"path": "/b", "methods": [{"method": "GET", "response_codes": {"200": 1, "500": 0}}]},
        ]
    }
    assert missing_responses(document, report) == [("/b", "get", "500")]
    report["endpoints"][1]["methods"][0]["response_codes"]["500"] = 1
    assert missing_responses(document, report) == []
