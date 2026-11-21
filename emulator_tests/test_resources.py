import json
import os
import ssl
import time
from pathlib import Path
from urllib.request import urlopen


def test_deployed_resources(aws, resources):
    path = "TsugiteApi/"
    bucket = resources[path + "Web/Resource"]
    s3 = aws.client("s3")
    assert all(s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
    index = Path("frontend/dist/index.html").read_bytes()
    s3.put_object(Bucket=bucket, Key="index.html", Body=index)
    assert s3.get_object(Bucket=bucket, Key="index.html")["Body"].read() == index
    secret = resources[path + "OriginKey/Resource"]
    assert aws.client("secretsmanager").get_secret_value(SecretId=secret)["SecretString"]
    logs = aws.client("logs")
    group = resources[path + "HttpAccessLog/Resource"]
    assert logs.describe_log_groups(logGroupNamePrefix=group)["logGroups"][0]["retentionInDays"] == 90
    gateway = aws.client("apigatewayv2")
    api_id = resources[path + "Gateway/Resource"]
    stage = gateway.get_stage(ApiId=api_id, StageName="$default")
    assert group in stage["AccessLogSettings"]["DestinationArn"]
    assert "requestId" in json.loads(stage["AccessLogSettings"]["Format"])
    functions = aws.client("lambda")
    name = resources[path + "Sample/Resource"]
    functions.get_waiter("function_active_v2").wait(
        FunctionName=name, WaiterConfig={"Delay": 1, "MaxAttempts": 30}
    )
    arn = functions.get_function_configuration(FunctionName=name)["FunctionArn"]
    functions.add_permission(
        FunctionName=name,
        StatementId="AllowStockRoute",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=f"arn:aws:execute-api:us-east-1:000000000000:{api_id}/*/GET/stock",
    )
    result = functions.invoke(FunctionName=name, Payload=b"{}")
    data = json.load(result["Payload"])
    assert "FunctionError" not in result, data
    integration = gateway.create_integration(
        ApiId=api_id, IntegrationType="AWS_PROXY", IntegrationUri=arn, PayloadFormatVersion="2.0"
    )
    gateway.create_route(
        ApiId=api_id, RouteKey="GET /stock", Target="integrations/" + integration["IntegrationId"]
    )
    api = gateway.get_api(ApiId=api_id)
    endpoint = api["ApiEndpoint"]
    assert endpoint.startswith(os.environ["AWS_ENDPOINT_URL"] + "/")
    with urlopen(
        endpoint + "/stock",
        context=ssl.create_default_context(cafile=os.environ["AWS_CA_BUNDLE"]),
        timeout=8,
    ) as r:
        assert json.load(r) == {"items": [{"sku": "TS-01", "stock": 12}]}


def test_create_dsql_cluster(aws):
    db = aws.client("dsql")
    cluster = db.create_cluster(deletionProtectionEnabled=True)
    for _ in range(40):
        state = db.get_cluster(identifier=cluster["identifier"])
        if state["status"] == "ACTIVE":
            break
        time.sleep(0.25)
    assert state["status"] == "ACTIVE" and state["deletionProtectionEnabled"]
    assert state["endpoint"] == "127.0.0.1"
