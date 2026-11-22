import json
from pathlib import Path

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template
from src.infra_app.stack import CatalogStack


def test_access_boundaries(tmp_path):
    stack = CatalogStack(
        App(outdir=str(tmp_path)),
        "TsugiteApi",
        env=Environment(account="111111111111", region="ap-northeast-1"),
    )
    template = Template.from_stack(stack)
    template.resource_count_is("AWS::EC2::NatGateway", 0)
    template.resource_count_is("AWS::DSQL::Cluster", 1)
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
    "AWS::Lambda::LayerVersion",
    "AWS::Lambda::Permission",
    "AWS::S3::BucketPolicy",
    "Custom::CDKBucketDeployment",
}


@pytest.mark.parametrize("custom", [False, True], ids=["sample", "custom-project"])
def test_every_resource_has_ownership(tmp_path, custom):
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
    stack = CatalogStack(App(outdir=str(tmp_path)), "TsugiteApi")
    resources = Template.from_stack(stack).to_json()["Resources"]
    old_groups = json.loads(Path(__file__).with_name("legacy_resources.json").read_text())
    for component, logical_ids in old_groups.items():
        for logical_id in logical_ids:
            assert resources[logical_id]["Metadata"]["Tsugite"]["Component"] == component
