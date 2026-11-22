import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import boto3
import pytest

from tests.e2e.aws.stock_functions import STOCK_FUNCTIONS

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def aws():
    endpoint = urlsplit(os.environ.get("AWS_ENDPOINT_URL", ""))
    if (endpoint.scheme, endpoint.hostname) != ("https", "127.0.0.1"):
        pytest.fail("tools/emulator_e2e.py から実行してください")
    return boto3.Session()


@pytest.fixture(scope="session")
def resources(aws, tmp_path_factory):
    assembly = ROOT / "packages/infra/cdk.out"
    template = json.loads((assembly / "TsugiteApi.template.json").read_text())
    kinds = {
        "AWS::S3::Bucket",
        "AWS::SecretsManager::Secret",
        "AWS::Logs::LogGroup",
        "AWS::ApiGatewayV2::Api",
        "AWS::ApiGatewayV2::Stage",
        "AWS::CloudFront::OriginAccessControl",
    }
    resources = template["Resources"]
    sample_ids = set(STOCK_FUNCTIONS.values())
    role_ids = {resources[name]["Properties"]["Role"]["Fn::GetAtt"][0] for name in sample_ids}
    ids = sample_ids | role_ids
    selected = {k: v for k, v in resources.items() if v["Type"] in kinds or k in ids}

    # Publish the synthesized file assets before CloudFormation creates the functions.
    manifest = json.loads((assembly / "TsugiteApi.assets.json").read_text())["files"]
    asset_bucket = "tsugite-emulator-file-assets"
    s3 = aws.client("s3")
    s3.create_bucket(Bucket=asset_bucket)
    archive_dir = tmp_path_factory.mktemp("stock-assets")
    for key in {selected[name]["Properties"]["Code"]["S3Key"] for name in sample_ids}:
        source = manifest[Path(key).stem]["source"]
        assert source["packaging"] == "zip"
        archive_base = archive_dir / Path(key).stem
        archive = shutil.make_archive(str(archive_base), "zip", assembly / source["path"])
        s3.upload_file(archive, asset_bucket, key)
    for name in sample_ids:
        selected[name]["Properties"]["Code"]["S3Bucket"] = asset_bucket
    stack = aws.client("cloudformation")
    name = "TsugiteEmulator"
    stack.create_stack(
        StackName=name, TemplateBody=json.dumps({"Resources": selected}), Capabilities=["CAPABILITY_IAM"]
    )
    stack.get_waiter("stack_create_complete").wait(
        StackName=name, WaiterConfig={"Delay": 1, "MaxAttempts": 60}
    )
    deployed = stack.list_stack_resources(StackName=name)["StackResourceSummaries"]
    assert {v["LogicalResourceId"] for v in deployed} == set(selected)
    assert all(v["ResourceStatus"] == "CREATE_COMPLETE" for v in deployed)
    physical = {v["LogicalResourceId"]: v["PhysicalResourceId"] for v in deployed}
    waiter = aws.client("lambda").get_waiter("function_active_v2")
    for name in sample_ids:
        waiter.wait(FunctionName=physical[name], WaiterConfig={"Delay": 1, "MaxAttempts": 30})
    return physical
