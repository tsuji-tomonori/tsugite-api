# API Gatewayのルーティングを定義する。
import json

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as gw
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integ
from aws_cdk import aws_logs as logs
from constructs import Construct


class CatalogGateway(Construct):
    def __init__(self, scope: Construct, key: str, prefix, api_fn, auth_fn):
        super().__init__(scope, key)
        api = gw.HttpApi(self, "Default", api_name="Gateway")
        backend = integ.HttpLambdaIntegration(
            "FastAPI", api_fn, payload_format_version=gw.PayloadFormatVersion.VERSION_2_0
        )
        gate = authorizers.HttpLambdaAuthorizer(
            "ProjectAccess",
            auth_fn,
            response_types=[authorizers.HttpLambdaResponseType.SIMPLE],
            results_cache_ttl=Duration.seconds(0),
        )
        api.add_routes(
            path=prefix + "/invoke/{proxy+}",
            methods=[gw.HttpMethod.ANY],
            integration=backend,
            authorizer=gate,
        )
        api.add_routes(path=prefix + "/{proxy+}", methods=[gw.HttpMethod.ANY], integration=backend)
        access_log = logs.LogGroup(self, "HttpAccessLog", retention=logs.RetentionDays.THREE_MONTHS)
        stage = api.default_stage.node.default_child
        stage.access_log_settings = gw.CfnStage.AccessLogSettingsProperty(
            destination_arn=access_log.log_group_arn,
            format=json.dumps(
                {
                    "requestId": "$context.requestId",
                    "route": "$context.routeKey",
                    "status": "$context.status",
                    "project": "$context.authorizer.project",
                    "subject": "$context.authorizer.subject",
                }
            ),
        )

        self.api = api
