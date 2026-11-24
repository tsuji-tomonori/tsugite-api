from unittest.mock import MagicMock

import pytest
from app import migrate


@pytest.mark.parametrize(
    "chat",
    [
        pytest.param(
            False, id="runtime", marks=pytest.mark.case_detail("既存の実行ロールだけを設定する")
        ),
        pytest.param(True, id="chat", marks=pytest.mark.case_detail("チャット用の読取ロールも設定する")),
    ],
)
def test_grants_public_tables_without_altering_the_schema(monkeypatch, chat):
    """移行時は public のスキーマ権限を変更せず、実行ロールに対象テーブルの権限を付与する"""
    engine = MagicMock()
    upgrade = MagicMock()
    monkeypatch.setattr(migrate, "engine", engine)
    monkeypatch.setattr(migrate.command, "upgrade", upgrade)
    connection = engine.return_value.connect.return_value.execution_options.return_value
    conn = connection.__enter__.return_value
    conn.scalar.return_value = None

    arn = "arn:aws:iam::123456789012:role/tsugite-runtime"
    event = {"RequestType": "Create", "ResourceProperties": {"RuntimeRoleArn": arn}}
    chat_arn = "arn:aws:iam::123456789012:role/tsugite-chat"
    if chat:
        event["ResourceProperties"]["ChatRoleArn"] = chat_arn
    result = migrate.handler(event, None)

    assert result == {"PhysicalResourceId": "tsugite-catalog-schema"}
    assert upgrade.call_args.args[1] == "head"
    statements = [call.args[0] for call in conn.exec_driver_sql.call_args_list]
    assert "CREATE ROLE tsugite_app WITH LOGIN" in statements
    assert f"AWS IAM GRANT tsugite_app TO '{arn}'" in statements
    assert all("ON SCHEMA public" not in statement for statement in statements)
    assert any(s.startswith("GRANT SELECT, INSERT, UPDATE ON assets,") for s in statements)
    assert "GRANT SELECT, INSERT, UPDATE ON portal_member_profiles TO tsugite_app" in statements
    assert any(s.startswith("GRANT SELECT, INSERT ON spec_releases, audit_events,") for s in statements)
    chat_grants = [s for s in statements if s.startswith("GRANT ") and s.endswith(" TO tsugite_chat")]
    assert chat_grants == (["GRANT SELECT ON assets, asset_routes TO tsugite_chat"] if chat else [])
    assert (f"AWS IAM GRANT tsugite_chat TO '{chat_arn}'" in statements) == chat
