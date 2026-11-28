"""実環境テストで使う認証コード・配信元・利用者照合を検証する。"""

import pytest

from tests.e2e.deployed.account import gateway_origin, is_test_consumer, portal_origin, totp


def test_totp_reference_vector() -> None:
    """RFC 6238 の公開テストベクトルから Cognito 用の6桁コードを生成する。"""
    assert totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59) == "287082"


def test_portal_origin() -> None:
    """スタック出力の HTTPS 配信元を受け付け、別ホストやパスを含む設定を拒否する。"""
    origin = "https://dexample.cloudfront.net"
    assert portal_origin(origin + "/") == origin
    for url in (origin + ".example.org", origin + "/login", origin.replace("https:", "http:")):
        with pytest.raises(ValueError, match="PortalUrl"):
            portal_origin(url)


def test_gateway_origin() -> None:
    """Bearerの送信先にはHTTPSのAPI Gateway標準エンドポイントだけを受け付ける。"""
    origin = "https://example123.execute-api.ap-northeast-1.amazonaws.com"
    assert gateway_origin(origin + "/") == origin
    for url in (
        "",
        origin + ".example.org",
        origin + "/path",
        origin + "?q",
        origin.replace("https:", "http:"),
    ):
        with pytest.raises(ValueError, match="GatewayEndpoint"):
            gateway_origin(url)


def test_only_expected_consumer() -> None:
    """専用ユーザーの識別子と一般利用者権限がすべて一致した場合に確認を通過する。"""
    profile = {
        "subject": "dedicated",
        "admin": False,
        "auditor": False,
        "projects": ["team"],
        "owners": ["team"],
        "leads": [],
    }
    assert is_test_consumer(profile, "dedicated")
    assert not is_test_consumer(profile, "other")
    for key, value in (("admin", True), ("auditor", True), ("owners", ["p"]), ("leads", ["p"])):
        assert not is_test_consumer({**profile, key: value}, "dedicated")
