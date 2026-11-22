import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from boto3.s3.transfer import TransferConfig

ROOT = Path(__file__).resolve().parents[3]
LAMBDA_ASSET = ROOT / "build/lambda"
WAITER = {"Delay": 1, "MaxAttempts": 60}


def test_deploy_migration_lambda(aws, tmp_path):
    """合成済みテンプレートから移行 Lambda を構築し、本番配布物のハンドラーを実行できる"""
    template = json.loads((ROOT / "packages/infra/cdk.out/TsugiteApi.template.json").read_text())
    resources = template["Resources"]
    logical_id, function = next(
        (name, spec)
        for name, spec in resources.items()
        if spec.get("Properties", {}).get("Handler") == "app.migrate.handler"
    )
    properties = function["Properties"]
    role = properties["Role"]["Fn::GetAtt"][0]
    log_group = properties["LoggingConfig"]["LogGroup"]["Ref"]

    bucket = "tsugite-emulator-migration-assets"
    archive = Path(shutil.make_archive(str(tmp_path / "migration"), "zip", LAMBDA_ASSET))
    s3 = aws.client("s3")
    s3.create_bucket(Bucket=bucket)
    part_size = 5 * 1024 * 1024
    s3.upload_file(
        str(archive),
        bucket,
        "migration.zip",
        Config=TransferConfig(multipart_threshold=part_size, multipart_chunksize=part_size),
    )
    properties["Code"] = {"S3Bucket": bucket, "S3Key": "migration.zip"}
    properties["Environment"]["Variables"]["DSQL_HOST"] = "127.0.0.1"
    function["DependsOn"] = [role]

    stack = aws.client("cloudformation")
    name = "TsugiteMigrationEmulator"
    stack.create_stack(
        StackName=name,
        TemplateBody=json.dumps(
            {"Resources": {role: resources[role], log_group: resources[log_group], logical_id: function}}
        ),
        Capabilities=["CAPABILITY_IAM"],
    )
    stack.get_waiter("stack_create_complete").wait(StackName=name, WaiterConfig=WAITER)
    deployed = stack.describe_stack_resource(StackName=name, LogicalResourceId=logical_id)
    physical_id = deployed["StackResourceDetail"]["PhysicalResourceId"]
    functions = aws.client("lambda")
    functions.get_waiter("function_active_v2").wait(FunctionName=physical_id, WaiterConfig=WAITER)
    result = functions.invoke(FunctionName=physical_id, Payload=b'{"RequestType":"Delete"}')
    data = json.load(result["Payload"])
    assert "FunctionError" not in result, data
    assert data == {"PhysicalResourceId": "tsugite-catalog-schema"}


def test_run_packaged_migration_on_postgresql(aws):
    """本番配布物の移行処理が DSQL 方言で全リビジョンを適用し、再実行できる"""
    pg_bin = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
    with TemporaryDirectory(prefix="tsugite-pg-") as directory:
        data_dir = Path(directory) / "data"
        subprocess.run(
            [
                pg_bin / "initdb",
                "-D",
                data_dir,
                "--username=admin",
                "--auth=trust",
                "--no-locale",
                "--encoding=UTF8",
            ],
            check=True,
            timeout=30,
        )
        control = [pg_bin / "pg_ctl", "-D", data_dir, "-w", "-t", "15"]
        subprocess.run(
            [
                *control,
                "-l",
                Path(directory) / "postgres.log",
                "-o",
                f"-h '' -k {shlex.quote(directory)}",
                "start",
            ],
            check=True,
            timeout=25,
        )
        try:
            runner = Path(__file__).with_name("migration_package.py")
            subprocess.run(
                [sys.executable, "-I", "-S", str(runner), str(LAMBDA_ASSET), directory],
                check=True,
                timeout=45,
            )
        finally:
            subprocess.run([*control, "-m", "fast", "stop"], check=True, timeout=25)
