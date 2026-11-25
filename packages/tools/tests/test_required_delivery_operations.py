# 配備手順とデモの公開契約を、外部プロセスやクラウドへ接続せずに検証する。
import json
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import httpx
import pytest
import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.tools.ci import audit_infra
from packages.tools.demo import seed_marketplace
from packages.tools.design import sample_openapi
from packages.tools.operations import bootstrap_admin, manage, sync_member_emails
from packages.tools.testing import emulator_e2e


@pytest.fixture
def managed(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(manage, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    for step in ("frontend", "backend", "chat", "publish_models"):
        monkeypatch.setattr(manage, step, lambda name=step: events.append(name))

    def run(command, *, check, **kwargs):
        assert check
        events.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    return events


@pytest.mark.parametrize(
    ("action", "options"),
    [
        pytest.param("synth", [], marks=pytest.mark.case_detail("合成ではモデルを配信しない")),
        pytest.param(
            "deploy",
            ["--require-approval", "any-change"],
            marks=pytest.mark.case_detail("配備では指定した承認条件とモデルを使用する"),
        ),
    ],
)
def test_cdk_receives_packaged_app_and_bindings(tmp_path, managed, monkeypatch, action, options):
    """独自の接続先を指定すると配布物を作り、その接続設定で合成または配備する。"""
    config = tmp_path / "接続例.json"
    config.write_text("{}")
    monkeypatch.setattr(sys, "argv", ["manage", action, "--bindings", config.name, *options])
    manage.main()
    steps, cdk = managed[:-1], managed[-1]
    assert set(steps) == {"frontend", "backend", "chat"} | (
        {"publish_models"} if action == "deploy" else set()
    )
    assert cdk[cdk.index("cdk") + 1] == action
    assert f"bindings={config}" in cdk
    if options:
        assert cdk[cdk.index("--require-approval") + 1] == "any-change"


def test_build_prepares_all_delivery_artifacts(managed, monkeypatch):
    """ビルドだけを選ぶとSPAとAPIとモデルの配布物を準備して終了する。"""
    monkeypatch.setattr(sys, "argv", ["manage", "build"])
    manage.main()
    assert sorted(managed) == ["backend", "chat", "frontend"]


def test_demo_uses_local_port_after_migration(managed, monkeypatch):
    """デモではDBを最新まで移行してから指定したループバックのポートでAPIを起動する。"""
    monkeypatch.setattr(sys, "argv", ["manage", "demo", "--port", "8561"])
    monkeypatch.setattr("os.environ", os.environ.copy())
    manage.main()
    frontend, migration, server = managed
    assert frontend == "frontend"
    assert "alembic" in migration and migration[-2:] == ["upgrade", "head"]
    assert "uvicorn" in server
    assert server[server.index("--host") + 1] == "127.0.0.1"
    assert server[server.index("--port") + 1] == "8561"


def test_seed_publishes_each_edition_and_reuses_existing_inventory():
    """二拠点に十二商品ずつ公開し、再投入時は未公開に戻った一商品だけを再公開する。"""
    inventory = {}
    creates = []
    publications = []

    def portal(request):
        if request.url.path == "/demo/provider":
            return httpx.Response(200, json={"access_token": "demo", "token": "demo"})
        if request.method == "GET" and request.url.path == "/apis":
            return httpx.Response(200, json=list(inventory.values()))
        if request.method == "POST" and request.url.path == "/apis":
            payload = json.loads(request.content)
            identifier = payload["slug"]
            assert identifier not in inventory
            creates.append(payload)
            inventory[identifier] = dict(payload, id=identifier, published=False)
            return httpx.Response(201, json=inventory[identifier])
        if request.method == "GET":
            return httpx.Response(200, json=inventory[request.url.path.split("/")[-1]])
        assert request.method == "PUT", str(request.url)
        prefix, identifier, operation = request.url.path.strip("/").split("/")
        assert (prefix, operation, request.url.params["published"]) == ("apis", "publication", "true")
        publications.append(identifier)
        inventory[identifier]["published"] = True
        return httpx.Response(200, json=inventory[identifier])

    with httpx.Client(base_url="http://demo.test", transport=httpx.MockTransport(portal)) as client:
        first = seed_marketplace.seed(client, 2)
        assert len(set(first)) == len(creates) == len(publications) == 24
        products = json.loads(
            (Path(__file__).resolve().parents[3] / "docs/examples/marketplace.json").read_text()
        )
        for product in products:
            offers = [o for o in creates if product["name"] in o["name"]]
            assert len(offers) == 2
            for offer in offers:
                matching = [
                    operations
                    for route, operations in offer["spec"]["paths"].items()
                    if re.fullmatch(re.sub(r"\{[^}]+}", "[^/]+", route), product["path"])
                ]
                assert any(product["method"].lower() in operations for operations in matching)
                assert product["environment"] in offer["targets"]
        inventory[first[-1]]["published"] = False
        publications.clear()
        assert set(seed_marketplace.seed(client, 2)) == set(first)
        assert len(creates) == 24
        assert publications == [first[-1]]


def test_audit_retains_the_generated_report(tmp_path, monkeypatch):
    """監査を実行すると合成で得たCSVの各指摘を成果物から読める。"""
    report = tmp_path / "AwsSolutions.csv"
    report.write_text("Rule ID,Compliance\nAwsSolutions-IAM5,Non-Compliant\n")
    monkeypatch.setattr(audit_infra, "ROOT", tmp_path)
    monkeypatch.setattr(audit_infra, "synthesize_report", lambda target: report)
    audit_infra.main()
    assert (tmp_path / "artifacts/cdk-nag.csv").read_bytes() == report.read_bytes()


def test_emulator_startup_failure_stops_before_pytest(tmp_path, monkeypatch):
    """専用のエミュレーターが起動中に終了したらテストを開始せずプロセスを回収する。"""
    binary = tmp_path / "aws-emulator"
    binary.touch(mode=0o755)
    monkeypatch.setenv("AWS_EMULATOR_BINARY", str(binary))
    process = Mock()
    process.poll.return_value = 1
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="AWS Emulator"):
        emulator_e2e.main()
    assert all("pytest" not in call.args[0] for call in run.call_args_list)
    process.wait.assert_called_once()


def test_directory_sync_previews_then_confirms_each_subject():
    """同期は件数だけを確認でき、反映時は同一メールの別人を区別し照合の失敗した属性を保存しない。"""
    pool = "directory-pool"
    database = create_engine("sqlite://")
    sync_member_emails.Member.metadata.create_all(database)

    def user(subject, key="Attributes"):
        return {
            "Username": subject,
            "Enabled": True,
            key: [
                {"Name": "sub", "Value": subject},
                {"Name": "email", "Value": "shared@example.test"},
                {"Name": "email_verified", "Value": "true"},
            ],
        }

    idp = Mock()
    idp.get_paginator.return_value.paginate.return_value = [
        {"Users": [user("person-a"), user("person-b")]},
        {"Users": [user("replaced"), {"Username": "incomplete", "Attributes": []}]},
    ]

    def confirm(*, UserPoolId, Username):
        assert UserPoolId == pool
        return user("replacement" if Username == "replaced" else Username, "UserAttributes")

    idp.admin_get_user.side_effect = confirm
    preview = sync_member_emails.sync(idp, database, pool)
    assert preview["changed"] == 3
    with Session(database) as db:
        assert db.scalars(select(sync_member_emails.MemberProfile)).all() == []
    applied = sync_member_emails.sync(idp, database, pool, apply=True)
    assert applied["changed"] == 2
    with Session(database) as db:
        profiles = db.scalars(select(sync_member_emails.MemberProfile)).all()
        assert {profile.subject: profile.email for profile in profiles} == {
            "person-a": "shared@example.test",
            "person-b": "shared@example.test",
        }
    assert sync_member_emails.sync(idp, database, pool)["current"] == 2


@pytest.mark.parametrize(
    ("flags", "apply", "label"),
    [
        pytest.param(
            [], False, "反映候補", marks=pytest.mark.case_detail("省略時は反映候補の件数を表示する")
        ),
        pytest.param(
            ["--apply"], True, "反映", marks=pytest.mark.case_detail("反映の指定時は保存件数を表示する")
        ),
    ],
)
def test_directory_command_reports_preview_or_apply(flags, apply, label, monkeypatch, capsys):
    """同期CLIは指定した環境と保存モードで照合し、運用者に処理の件数を表示する。"""
    for key in ("HUB_SETTINGS_PARAMETER", "DSQL_HOST", "DSQL_USER"):
        monkeypatch.setenv(key, "fixture")
    idp, database = Mock(), Mock()
    monkeypatch.setattr(sync_member_emails, "settings", lambda: {"pool_id": "pool-test"})
    monkeypatch.setattr(sync_member_emails, "engine", lambda: database)
    monkeypatch.setattr(sync_member_emails.boto3, "client", lambda name: idp)
    sync = Mock(return_value={"changed": 5, "current": 2, "skipped": 1})
    monkeypatch.setattr(sync_member_emails, "sync", sync)
    monkeypatch.setattr(sys, "argv", ["sync_member_emails", *flags])
    sync_member_emails.main()
    sync.assert_called_once_with(idp, database, "pool-test", apply=apply)
    output = capsys.readouterr().out
    assert f"{label} 5件" in output and "2件" in output and "1件" in output


def test_emulator_runs_selected_tests_then_removes_credentials(tmp_path, monkeypatch):
    """ヘルスチェックに成功すると隔離環境でpytestを起動し、失敗コードを返して専用資格情報を破棄する。"""
    executable = tmp_path / "aws-emulator"
    executable.touch(mode=0o755)
    monkeypatch.setenv("AWS_EMULATOR_BINARY", str(executable))
    monkeypatch.setattr(sys, "argv", ["emulator_e2e", "--junitxml=aws.xml", "-k", "deployment"])
    emulator = Mock()
    emulator.poll.return_value = None
    test_process = MagicMock()
    test_process.__enter__.return_value.wait.return_value = 7
    environments = {}

    def launch(command, *, env):
        if command[0] == str(executable):
            port = command[command.index("-p") + 1]
            home = Path(env["HOME"])
            config = home / ".aws/emulator" / port
            config.mkdir(parents=True)
            for name in ("config", "emulator_credentials", "ca.pem"):
                (config / name).write_text("local test data")
            environments["directory"] = home
            environments["port"] = port
            return emulator
        assert "pytest" in command and "tests/e2e/aws" in command
        assert command[-3:] == ["--junitxml=aws.xml", "-k", "deployment"]
        environments["tests"] = env
        return test_process

    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0)))
    monkeypatch.setattr(emulator_e2e.ssl, "create_default_context", Mock())
    response = MagicMock()
    response.__enter__.return_value.status = 200
    health = Mock(return_value=response)
    monkeypatch.setattr(emulator_e2e, "urlopen", health)
    assert emulator_e2e.main() == 7
    port = environments["port"]
    assert health.call_args.args[0] == f"https://127.0.0.1:{port}/__admin/health"
    assert str(environments["directory"]) in environments["tests"]["AWS_SHARED_CREDENTIALS_FILE"]
    emulator.terminate.assert_called_once()
    emulator.wait.assert_called_once()
    assert not environments["directory"].exists()


def test_sample_api_documents_follow_catalog_and_remove_retired_files(tmp_path):
    """見本商品の仕様を更新すると各商品に日本語の操作とスキーマが揃い、廃止した仕様は消える。"""
    catalog = json.loads(
        (Path(__file__).resolve().parents[3] / "docs/examples/marketplace.json").read_bytes()
    )
    retired = tmp_path / "retired.yaml"
    retired.write_text("old")
    sample_openapi.generate(tmp_path)
    assert {p.stem for p in tmp_path.glob("*.yaml")} == {product["slug"] for product in catalog}
    for product in catalog:
        doc = yaml.safe_load((tmp_path / f"{product['slug']}.yaml").read_text())
        assert doc["info"]["title"] == product["name"]
        assert doc["openapi"].startswith("3.")
        assert doc["components"]["schemas"]
        assert any(
            re.search(r"[ぁ-んァ-ヶ一-龠]", operation["summary"])
            for path, methods in doc["paths"].items()
            if path != "/health"
            for operation in methods.values()
        )


def test_contracts_command_exports_openapi_and_column_names(tmp_path, monkeypatch):
    """契約の生成を選ぶとAPIの操作とテーブルの日本語カラム定義をJSONで取得できる。"""
    monkeypatch.syspath_prepend(str(manage.ROOT))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(manage, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["manage", "contracts"])
    manage.main()
    api = json.loads((tmp_path / "artifacts/openapi.json").read_bytes())
    assert api["openapi"].startswith("3.") and "get" in api["paths"]["/api/health"]
    tables = json.loads((tmp_path / "artifacts/tables.json").read_bytes())
    columns = {column["column"]: column["column_name_ja"] for column in tables["access_rights"]}
    assert columns["id"] == "利用権の識別子"


def test_emulator_timeout_cleans_up_without_running_pytest(tmp_path, monkeypatch):
    """エミュレーターが認証情報を準備しない場合は待機を打ち切り、pytestを起動せず終了する。"""
    binary = tmp_path / "aws-emulator"
    binary.touch(mode=0o755)
    monkeypatch.setenv("AWS_EMULATOR_BINARY", str(binary))
    proc = Mock()
    proc.poll.return_value = None
    start = Mock(return_value=proc)
    monkeypatch.setattr(subprocess, "Popen", start)
    monkeypatch.setattr(subprocess, "run", Mock())
    monkeypatch.setattr(emulator_e2e.time, "sleep", lambda seconds: None)
    with pytest.raises(TimeoutError, match="AWS Emulator"):
        emulator_e2e.main()
    start.assert_called_once()
    proc.terminate.assert_called_once()
    proc.wait.assert_called_once()
    assert not Path(start.call_args.kwargs["env"]["HOME"]).exists()


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(
            "invite", marks=pytest.mark.case_detail("既存の管理者がいると招待メールを送信しない")
        ),
        pytest.param("grant", marks=pytest.mark.case_detail("既存の管理者がいるとグループを変更しない")),
    ],
)
def test_bootstrap_workflow_can_be_retried_without_changing_admins(action, tmp_path, monkeypatch):
    """初回登録の各ジョブを再実行しても、既存の管理者がいればCognitoの更新を行わない。"""
    pool = "local-pool"

    def aws(args, **kwargs):
        service, operation = args[1:3]
        if (service, operation) == ("cloudformation", "describe-stacks"):
            response = {"Stacks": [{"Outputs": [{"OutputKey": "UserPoolId", "OutputValue": pool}]}]}
        else:
            assert (service, operation) == ("cognito-idp", "list-users-in-group")
            assert args[args.index("--user-pool-id") + 1] == pool
            assert args[args.index("--group-name") + 1] == "admin"
            response = {"Users": [{"Username": "current-admin"}]}
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(response))

    monkeypatch.setattr(subprocess, "run", aws)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "operator@example.test")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("INVITED_POOL", pool)
    monkeypatch.setenv("INVITED_SUBJECT", "previously-invited")
    monkeypatch.setattr(sys, "argv", ["bootstrap", action])
    runpy.run_path(bootstrap_admin.__file__, run_name="__main__")
