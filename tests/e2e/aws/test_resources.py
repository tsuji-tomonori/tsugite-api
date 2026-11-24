import json
import os
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


def test_deployed_resources(aws, resources):
    """構築したS3・API Gateway・Lambdaのタグを取得し、在庫APIが商品を返す"""
    bucket = resources["Web3C8945DB"]
    s3 = aws.client("s3")
    assert all(s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
    assert {t["Key"]: t["Value"] for t in s3.get_bucket_tagging(Bucket=bucket)["TagSet"]}.items() >= {
        "Application": "TsugiteAPI",
        "ManagedBy": "AWS-CDK",
        "Component": "Portal",
    }.items()
    index = Path("packages/frontend/dist/index.html").read_bytes()
    s3.put_object(Bucket=bucket, Key="index.html", Body=index)
    assert s3.get_object(Bucket=bucket, Key="index.html")["Body"].read() == index
    secret = resources["OriginKey10CF34FB"]
    assert aws.client("secretsmanager").get_secret_value(SecretId=secret)["SecretString"]
    logs = aws.client("logs")
    group = resources["HttpAccessLog2F8A15F0"]
    assert logs.describe_log_groups(logGroupNamePrefix=group)["logGroups"][0]["retentionInDays"] == 90
    gateway = aws.client("apigatewayv2")
    api_id = resources["Gateway43CB3636"]
    stage = gateway.get_stage(ApiId=api_id, StageName="$default")
    assert group in stage["AccessLogSettings"]["DestinationArn"]
    assert "requestId" in json.loads(stage["AccessLogSettings"]["Format"])
    functions = aws.client("lambda")
    name = resources["Sample9DACD4DE"]
    functions.get_waiter("function_active_v2").wait(
        FunctionName=name, WaiterConfig={"Delay": 1, "MaxAttempts": 30}
    )
    arn = functions.get_function_configuration(FunctionName=name)["FunctionArn"]
    transport = resources["transport-sandbox"]
    transport_arn = functions.get_function_configuration(FunctionName=transport)["FunctionArn"]
    functions.add_permission(
        FunctionName=transport,
        StatementId="AllowStockRoute",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=f"arn:aws:execute-api:us-east-1:000000000000:{api_id}/*/GET/items",
    )
    integration = gateway.create_integration(
        ApiId=api_id,
        IntegrationType="AWS_PROXY",
        IntegrationUri=transport_arn,
        PayloadFormatVersion="2.0",
    )
    gateway.create_route(
        ApiId=api_id, RouteKey="GET /items", Target="integrations/" + integration["IntegrationId"]
    )
    api = gateway.get_api(ApiId=api_id)
    assert api["Tags"]["Component"] == "Gateway"
    assert functions.list_tags(Resource=arn)["Tags"]["Component"] == "Bindings"
    endpoint = api["ApiEndpoint"]
    assert endpoint.startswith(os.environ["AWS_ENDPOINT_URL"] + "/")
    with urlopen(
        endpoint + "/items",
        context=ssl.create_default_context(cafile=os.environ["AWS_CA_BUNDLE"]),
        timeout=8,
    ) as r:
        assert json.load(r) == {"items": [{"sku": "TS-01", "stock": 12}]}


def test_create_dsql_cluster(aws):
    """DSQLクラスターが削除保護付きで稼働状態になる"""
    db = aws.client("dsql")
    cluster = db.create_cluster(deletionProtectionEnabled=True)
    for _ in range(40):
        state = db.get_cluster(identifier=cluster["identifier"])
        if state["status"] == "ACTIVE":
            break
        time.sleep(0.25)
    assert state["status"] == "ACTIVE" and state["deletionProtectionEnabled"]
    assert state["endpoint"] == "127.0.0.1"


def test_openapi_archive_versions(aws, resources, monkeypatch):
    """公開時にOpenAPI仕様の世代をS3に個別保存する"""
    from app.integrations.spec_archive import archive_spec

    from tests.support.catalog import SPEC

    bucket = next(v for k, v in resources.items() if k.startswith("RuntimeSpecifications"))
    monkeypatch.setenv("SPEC_BUCKET", bucket)
    digest = archive_spec("warehouse", SPEC)
    assert archive_spec("warehouse", SPEC) == digest
    key = f"specs/warehouse/{digest}.json"
    s3 = aws.client("s3")
    assert json.load(s3.get_object(Bucket=bucket, Key=key)["Body"]) == SPEC
    assert len(s3.list_object_versions(Bucket=bucket, Prefix=key)["Versions"]) == 1


def test_packaged_sample_products(resources, tmp_path):
    """登録済みのLambda配布ZIPをCPythonで実行し、全商品のヘルスチェックと業務応答を検証する。"""
    from tools.demo.seed_marketplace import CATALOG

    with ZipFile(resources["sample-package"]) as archive:
        archive.extractall(tmp_path)
    events = []
    for product in CATALOG:
        for method, suffix in (("GET", "/health"), (product["method"], product["path"])):
            path = f"/{product['slug']}{suffix}"
            events.append(
                {
                    "version": "2.0",
                    "headers": {"content-type": "application/json"},
                    "rawPath": path,
                    "rawQueryString": "",
                    "body": '{"units": 7}' if method == "POST" else None,
                    "requestContext": {
                        "http": {"method": method, "path": path, "sourceIp": "127.0.0.1"}
                    },
                }
            )
    runner = Path(__file__).with_name("sample_package.py")
    process = subprocess.run(
        [sys.executable, "-I", "-S", str(runner), str(tmp_path)],
        input=json.dumps(events),
        capture_output=True,
        text=True,
        check=True,
    )
    for event, line in zip(events, process.stdout.splitlines(), strict=True):
        payload = json.loads(line)
        assert payload["statusCode"] == 200, (event, payload)
        result = json.loads(payload["body"])
        assert result
        if event["rawPath"].endswith("/health"):
            assert result == {"status": "ok"}
