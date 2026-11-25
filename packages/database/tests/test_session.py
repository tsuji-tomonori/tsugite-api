# Aurora DSQL 接続では Amazon ルート CA を含むバンドルで証明書とホスト名を検証する。
import ssl
from unittest.mock import patch

import certifi
from tsugite_db.session import engine


def test_dsql_uses_a_bundled_ca_for_full_tls_verification(monkeypatch):
    """Aurora DSQL 接続では Amazon ルート CA を含むバンドルで証明書とホスト名を検証する。"""
    host = "example.dsql.ap-northeast-1.on.aws"
    monkeypatch.setenv("DSQL_HOST", host)
    monkeypatch.setenv("DSQL_USER", "admin")

    engine.cache_clear()
    try:
        with patch("aurora_dsql_sqlalchemy.create_dsql_engine") as create_dsql_engine:
            assert engine() is create_dsql_engine.return_value
    finally:
        engine.cache_clear()

    assert create_dsql_engine.call_args.kwargs["host"] == host
    assert create_dsql_engine.call_args.kwargs["sslmode"] == "verify-full"
    ca_file = create_dsql_engine.call_args.kwargs["sslrootcert"]
    assert ca_file == certifi.where()
    ca_certs = ssl.create_default_context(cafile=ca_file).get_ca_certs()
    assert any(("commonName", "Amazon Root CA 1") in rdn for cert in ca_certs for rdn in cert["subject"])
