import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import boto3
import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def aws():
    endpoint = urlsplit(os.environ.get("AWS_ENDPOINT_URL", ""))
    if (endpoint.scheme, endpoint.hostname) != ("https", "127.0.0.1"):
        pytest.fail("tools/emulator_e2e.py から実行してください")
    return boto3.Session()


@pytest.fixture(scope="session")
def resources(aws):
    template = json.loads((ROOT / "packages/infra/cdk.out/TsugiteApi.template.json").read_text())
    kinds = {
        "AWS::S3::Bucket",
        "AWS::SecretsManager::Secret",
        "AWS::Logs::LogGroup",
        "AWS::ApiGatewayV2::Api",
        "AWS::ApiGatewayV2::Stage",
        "AWS::CloudFront::OriginAccessControl",
    }
    selected = {
        k: v for k, v in template["Resources"].items() if v["Type"] in kinds or k.startswith("Sample")
    }
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
    return {v["LogicalResourceId"]: v["PhysicalResourceId"] for v in deployed}
