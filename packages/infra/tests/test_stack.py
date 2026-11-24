# 非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである。
import json
from pathlib import Path

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template
from src.infra_app.stack import CatalogStack


def test_access_boundaries(tmp_path, request):
    """非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである"""
    stack = CatalogStack(
        App(outdir=str(tmp_path)),
        "TsugiteApi",
        env=Environment(account="111111111111", region="ap-northeast-1"),
    )
    template = Template.from_stack(stack)
    nat_count = len(template.find_resources("AWS::EC2::NatGateway"))
    request.node.user_properties.append(
        ("measurement", f"AWS::EC2::NatGateway　期待 0 件 / 実測 {nat_count} 件")
    )
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "AllowedOAuthFlows": ["code"],
            "ExplicitAuthFlows": Match.array_with(["ALLOW_USER_PASSWORD_AUTH"]),
            "PreventUserExistenceErrors": "ENABLED",
        },
    )
    template.resource_count_is("AWS::EC2::NatGateway", 0)
    template.resource_count_is("AWS::DSQL::Cluster", 1)
    (schema,) = template.find_resources(
        "AWS::CloudFormation::CustomResource", {"Properties": {"Revision": Match.any_value()}}
    )
    functions = template.find_resources("AWS::Lambda::Function")
    for handler in ("app.main.handler", "app.authorizer.handler"):
        (runtime,) = (f for f in functions.values() if f["Properties"].get("Handler") == handler)
        assert schema in runtime["DependsOn"]
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Authorizer", {"AuthorizerResultTtlInSeconds": 0}
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "ANY /api/invoke/{proxy+}", "AuthorizationType": "CUSTOM"},
    )
    template.has_resource_properties(
        "AWS::Cognito::UserPool", {"AdminCreateUserConfig": {"AllowAdminCreateUserOnly": True}}
    )
    template.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": {
                "CacheBehaviors": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "PathPattern": "api/*",
                                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                            }
                        )
                    ]
                )
            }
        },
    )
    template.resource_count_is("AWS::CloudFront::OriginAccessControl", 1)
    template.resource_count_is("Custom::AWSCDKOpenIdConnectProvider", 0)
    template.has_resource_properties(
        "AWS::DSQL::Cluster", {"Tags": Match.array_with([{"Key": "Application", "Value": "TsugiteAPI"}])}
    )


# Resource types in this application whose CloudFormation schema has no tag property.
NO_RESOURCE_TAGS = {
    "AWS::ApiGatewayV2::Authorizer",
    "AWS::ApiGatewayV2::Integration",
    "AWS::ApiGatewayV2::Route",
    "AWS::CDK::Metadata",
    "AWS::CloudFormation::CustomResource",
    "AWS::CloudFront::OriginAccessControl",
    "AWS::Cognito::UserPoolClient",
    "AWS::Cognito::UserPoolDomain",
    "AWS::Cognito::UserPoolGroup",
    "AWS::Cognito::UserPoolResourceServer",
    "AWS::IAM::Policy",
    "AWS::Lambda::EventInvokeConfig",
    "AWS::Lambda::LayerVersion",
    "AWS::Lambda::Permission",
    "AWS::S3::BucketPolicy",
    "Custom::CDKBucketDeployment",
}


@pytest.mark.parametrize(
    "custom",
    [
        pytest.param(False, id="sample", marks=pytest.mark.case_detail("サンプル付きの標準構成を検証")),
        pytest.param(
            True, id="custom-project", marks=pytest.mark.case_detail("独自プロジェクト構成を検証")
        ),
    ],
)
def test_every_resource_has_ownership(tmp_path, custom):
    """すべてのリソースに管理情報を付け、タグ対応リソースには同じ値を付ける"""
    config = tmp_path / "bindings.json"
    config.write_text(json.dumps({"projects": ["warehouse-team"], "targets": {}}))
    app = App(outdir=str(tmp_path / "out"), context={"bindings": str(config)} if custom else {})
    stack = CatalogStack(app, "TsugiteApi", analytics_reporting=True)
    resources = Template.from_stack(stack).to_json()["Resources"]
    for logical_id, resource in resources.items():
        ownership = resource.get("Metadata", {}).get("Tsugite")
        assert ownership is not None, logical_id
        assert ownership["Application"] == "TsugiteAPI" and ownership["ManagedBy"] == "AWS-CDK", (
            logical_id
        )
        assert ownership["Component"] in {
            "Database",
            "Runtime",
            "Gateway",
            "Portal",
            "Identities",
            "Bindings",
            "Stack",
            "Chat",
        }, logical_id
        props = resource.get("Properties", {})
        tags = props.get("UserPoolTags", props.get("Tags"))
        if resource["Type"] in NO_RESOURCE_TAGS:
            assert tags is None, logical_id
        else:
            if isinstance(tags, list):
                tags = {tag["Key"]: tag["Value"] for tag in tags}
            assert tags is not None and ownership.items() <= tags.items(), logical_id
    if custom:
        assert "usewarehouseteam" in resources and "Sample9DACD4DE" not in resources


def test_existing_resources_keep_their_logical_ids(tmp_path):
    """既存リソースの論理IDと分割後の所属が対応する"""
    stack = CatalogStack(App(outdir=str(tmp_path)), "TsugiteApi")
    resources = Template.from_stack(stack).to_json()["Resources"]
    old_groups = json.loads(Path(__file__).with_name("legacy_resources.json").read_text())
    for component, logical_ids in old_groups.items():
        for logical_id in logical_ids:
            assert resources[logical_id]["Metadata"]["Tsugite"]["Component"] == component


def test_upstream_bindings_validate_target_and_secret(tmp_path):
    """提供先の所有者・環境・種類とARNを検査し、不正な接続設定で配備を進めない。"""
    target = {
        "owner": "team",
        "environment": "sandbox",
        "kind": "https",
        "address": "https://example.test",
    }
    config = tmp_path / "bindings.json"
    for index, (change, message) in enumerate(
        (
            ({"owner": "other"}, "owner or environment"),
            ({"environment": "other"}, "owner or environment"),
            ({"kind": "other"}, "unknown target"),
            ({"kind": "lambda", "address": "*"}, "specific Lambda ARN"),
            ({"secret_arn": "*"}, "specific secret ARN"),
        )
    ):
        config.write_text(json.dumps({"projects": ["team"], "targets": {"target": target | change}}))
        app = App(outdir=str(tmp_path / str(index)), context={"bindings": str(config)})
        with pytest.raises(ValueError, match=message):
            CatalogStack(app, "TsugiteApi")
