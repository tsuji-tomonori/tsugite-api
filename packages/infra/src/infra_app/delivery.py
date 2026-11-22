from aws_cdk import Stack
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as deploy
from constructs import Construct

from .functions import ROOT


class PortalDelivery(Construct):
    def __init__(self, scope: Construct, key: str, prefix, api, secret):
        super().__init__(scope, key)
        bucket = s3.Bucket(
            self,
            "Web",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
        static = cf.BehaviorOptions(
            origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
            viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        )
        distribution = cf.Distribution(
            self,
            "Default",
            default_root_object="index.html",
            default_behavior=static,
            additional_behaviors={
                prefix.lstrip("/") + "/*": cf.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        api.api_id
                        + ".execute-api."
                        + Stack.of(self).region
                        + "."
                        + Stack.of(self).url_suffix,
                        custom_headers={"X-Tsugite-Origin": secret.secret_value.unsafe_unwrap()},
                    ),
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.HTTPS_ONLY,
                )
            },
        )
        deploy.BucketDeployment(
            self,
            "WebFiles",
            sources=[deploy.Source.asset(str(ROOT / "packages/frontend/dist"))],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )
        self.url = "https://" + distribution.distribution_domain_name + "/"
