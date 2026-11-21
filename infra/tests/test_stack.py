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
