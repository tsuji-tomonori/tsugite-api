"""管理者がいないときだけメールで招待し、作成したユーザーの識別子を次のジョブに渡す。"""

import json
import subprocess
from unittest.mock import Mock, call

import pytest

from packages.tools.operations import bootstrap_admin as bootstrap

POOL = "ap-northeast-1_Example"
SUB = "b7ec89ba-2203-4fae-8a5c-3b7739f5e650"
EMAIL = "owner@example.org"
STACK = {"Stacks": [{"Outputs": [{"OutputKey": "UserPoolId", "OutputValue": POOL}]}]}
LIST = call(
    "cognito-idp",
    "list-users-in-group",
    "--user-pool-id",
    POOL,
    "--group-name",
    "admin",
    "--max-items",
    "1",
)
LOOKUP = call("cloudformation", "describe-stacks", "--stack-name", "TsugiteApi")
SUB_ATTR = {"Name": "sub", "Value": SUB}


def test_invite_delivers_password_by_email(monkeypatch, tmp_path):
    """管理者がいないときだけメールで招待し、作成したユーザーの識別子を次のジョブに渡す。"""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    aws = Mock(side_effect=[STACK, {"Users": []}, {"User": {"Attributes": [SUB_ATTR]}}])
    monkeypatch.setattr(bootstrap, "aws", aws)
    bootstrap.invite(EMAIL)
    assert aws.call_args_list == [
        LOOKUP,
        LIST,
        call(
            "cognito-idp",
            "admin-create-user",
            "--user-pool-id",
            POOL,
            "--username",
            EMAIL,
            "--user-attributes",
            json.dumps([{"Name": "email", "Value": EMAIL}]),
            "--desired-delivery-mediums",
            "EMAIL",
        ),
    ]
    assert output.read_text().splitlines() == [f"pool={POOL}", f"subject={SUB}"]


def test_existing_admin_skips_writes_in_both_jobs(monkeypatch):
    """管理者が既にいるときは招待と権限付与の両方を省く。"""
    aws = Mock(side_effect=[STACK, {"Users": [{}]}, STACK, {"Users": [{}]}])
    monkeypatch.setattr(bootstrap, "aws", aws)
    bootstrap.invite(EMAIL)
    bootstrap.grant(POOL, SUB, EMAIL)
    assert aws.call_args_list == [LOOKUP, LIST, LOOKUP, LIST]


def test_collision_never_adopts_an_existing_account(monkeypatch, tmp_path):
    """同名ユーザーが存在して作成に失敗したときは権限付与用の出力を残さない。"""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    aws = Mock(side_effect=[STACK, {"Users": []}, SystemExit("admin-create-user")])
    monkeypatch.setattr(bootstrap, "aws", aws)
    with pytest.raises(SystemExit, match="admin-create-user"):
        bootstrap.invite(EMAIL)
    assert not output.exists()


def test_grant_only_invited_user(monkeypatch):
    """招待と同じプールとユーザーなら初回ログイン用の管理権限を付与する。"""
    aws = Mock(side_effect=[STACK, {"Users": []}, {"UserAttributes": [SUB_ATTR]}, None])
    monkeypatch.setattr(bootstrap, "aws", aws)
    bootstrap.grant(POOL, SUB, EMAIL)
    assert aws.call_args_list == [
        LOOKUP,
        LIST,
        call("cognito-idp", "admin-get-user", "--user-pool-id", POOL, "--username", EMAIL),
        call(
            "cognito-idp",
            "admin-add-user-to-group",
            "--user-pool-id",
            POOL,
            "--username",
            EMAIL,
            "--group-name",
            "admin",
        ),
    ]


def test_replaced_user_cannot_be_promoted(monkeypatch):
    """招待後に同名の別ユーザーに置き換わったときは権限を付与しない。"""
    aws = Mock(
        side_effect=[STACK, {"Users": []}, {"UserAttributes": [{"Name": "sub", "Value": "other"}]}]
    )
    monkeypatch.setattr(bootstrap, "aws", aws)
    with pytest.raises(SystemExit, match="識別子"):
        bootstrap.grant(POOL, SUB, EMAIL)
    assert aws.call_count == 3


def test_pool_replacement_stops_grant(monkeypatch):
    """招待後にスタックのプールが置き換わったときはユーザーを操作しない。"""
    aws = Mock(return_value=STACK)
    monkeypatch.setattr(bootstrap, "aws", aws)
    with pytest.raises(SystemExit, match="プール"):
        bootstrap.grant("old", SUB, EMAIL)
    assert aws.call_args_list == [LOOKUP]


def test_missing_recipient_stops_before_creation(monkeypatch):
    """招待先を設定していないときはアカウントを作成しない。"""
    aws = Mock(side_effect=[STACK, {"Users": []}])
    monkeypatch.setattr(bootstrap, "aws", aws)
    with pytest.raises(SystemExit, match="BOOTSTRAP_ADMIN_EMAIL"):
        bootstrap.invite("")
    assert aws.call_args_list == [LOOKUP, LIST]


def test_cli_returns_json_and_handles_empty_responses(monkeypatch):
    """AWS CLI の照会結果を読み取り、グループ追加で応答が空でも成功する。"""
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, '{"Users": []}'),
            subprocess.CompletedProcess([], 0, ""),
        ]
    )
    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    assert bootstrap.aws("cognito-idp", "list-users-in-group") == {"Users": []}
    assert bootstrap.aws("cognito-idp", "admin-add-user-to-group") is None


def test_cli_error_hides_invitation_address(monkeypatch):
    """AWS CLI が失敗したときは操作名を示し、引数の招待先を例外に含めない。"""
    monkeypatch.setattr(
        bootstrap.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 254))
    )
    with pytest.raises(SystemExit, match="admin-create-user") as error:
        bootstrap.aws("cognito-idp", "admin-create-user", "--user-attributes", EMAIL)
    assert EMAIL not in str(error.value)
