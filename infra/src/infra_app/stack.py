import hashlib
import json
import tomllib
from pathlib import Path

from aws_cdk import (
    ArnFormat,
    CfnOutput,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_apigatewayv2 as gw,
)
from aws_cdk import (
    aws_apigatewayv2_authorizers as authorizers,
)
from aws_cdk import (
    aws_apigatewayv2_integrations as integ,
)
from aws_cdk import (
    aws_cloudfront as cf,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_cognito as cog,
)
from aws_cdk import (
    aws_dsql as dsql,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as fn,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as deploy,
)
from aws_cdk import (
    aws_secretsmanager as sm,
)
from aws_cdk import (
    aws_ssm as ssm,
)
from aws_cdk import (
    custom_resources as cr,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parents[3]


class CatalogStack(Stack):
    def __init__(self, scope: Construct, key: str, **kwargs):
        super().__init__(scope, key, **kwargs)
        Tags.of(self).add("Application", "TsugiteAPI")
        prefix = tomllib.loads((ROOT / "contracts/http.toml").read_text())["api_prefix"]
        config_file = self.node.try_get_context("bindings")
        cfg = json.loads(Path(config_file).read_text()) if config_file else {}
        projects = cfg.get("projects", ["supply", "finance"])
        if not projects or len(set(projects)) != len(projects):
            raise ValueError("projects must contain unique project names")
        import re

        if any(not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", p) for p in projects):
            raise ValueError("invalid project name")
        cluster = dsql.CfnCluster(self, "Database", deletion_protection_enabled=True)
        cluster.apply_removal_policy(RemovalPolicy.RETAIN)
        secret = sm.Secret(
            self, "OriginKey", generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True)
        )
        role = iam.Role(self, "RuntimeRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        runtime = fn.Runtime.PYTHON_3_14
        code = fn.Code.from_asset(str(ROOT / "build/lambda"))
        param = "/" + self.stack_name + "/portal"
        runtime_env = {
            "DSQL_HOST": cluster.attr_endpoint,
            "DSQL_USER": "tsugite_app",
            "HUB_SETTINGS_PARAMETER": param,
            "ORIGIN_SECRET": secret.secret_value.unsafe_unwrap(),
        }
        role.add_to_policy(
            iam.PolicyStatement(actions=["dsql:DbConnect"], resources=[cluster.attr_resource_arn])
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name=param.lstrip("/"),
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    )
                ],
            )
        )

        def function(name, handler, env, execution_role=None):
            group = logs.LogGroup(self, name + "Logs", retention=logs.RetentionDays.ONE_MONTH)
            f = fn.Function(
                self,
                name,
                runtime=runtime,
                handler=handler,
                code=code,
                environment=env,
                role=execution_role,
                timeout=Duration.seconds(60),
                memory_size=768,
                log_group=group,
            )
            group.grant_write(f)
            return f

        api_fn = function("Api", "app.main.handler", runtime_env, role)
        auth_fn = function("Access", "app.authorizer.handler", runtime_env, role)
        migration = function(
            "Migration",
            "app.migrate.handler",
            {"DSQL_HOST": cluster.attr_endpoint, "DSQL_USER": "admin"},
        )
        migration.add_to_role_policy(
            iam.PolicyStatement(actions=["dsql:DbConnectAdmin"], resources=[cluster.attr_resource_arn])
        )
        provider = cr.Provider(self, "SchemaProvider", on_event_handler=migration)
        digest = hashlib.sha256()
        for path in sorted((ROOT / "backend/migrations").rglob("*.py")):
            digest.update(path.read_bytes())
        digest.update((ROOT / "backend/src/app/migrate.py").read_bytes())
        CustomResource(
            self,
            "Schema",
            service_token=provider.service_token,
            properties={"Revision": digest.hexdigest(), "RuntimeRoleArn": role.role_arn},
        )

        api = gw.HttpApi(self, "Gateway")
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
            "Portal",
            default_root_object="index.html",
            default_behavior=static,
            additional_behaviors={
                prefix.lstrip("/") + "/*": cf.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        api.api_id + ".execute-api." + self.region + "." + self.url_suffix,
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
            sources=[deploy.Source.asset(str(ROOT / "frontend/dist"))],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )
        url = "https://" + distribution.distribution_domain_name + "/"
        pool = cog.UserPool(
            self,
            "Identities",
            self_sign_up_enabled=False,
            mfa=cog.Mfa.REQUIRED,
            mfa_second_factor=cog.MfaSecondFactor(otp=True, sms=False),
            password_policy=cog.PasswordPolicy(
                min_length=14,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            sign_in_aliases=cog.SignInAliases(username=True),
            removal_policy=RemovalPolicy.RETAIN,
        )
        domain = pool.add_domain(
            "Login",
            cognito_domain=cog.CognitoDomainOptions(
                domain_prefix="tsugite-"
                + self.account
                + "-"
                + self.region
                + "-"
                + hashlib.sha256(self.stack_name.encode()).hexdigest()[:6]
            ),
        )
        portal = pool.add_client(
            "WebClient",
            generate_secret=False,
            o_auth=cog.OAuthSettings(
                flows=cog.OAuthFlows(authorization_code_grant=True),
                scopes=[cog.OAuthScope.OPENID],
                callback_urls=[url],
                logout_urls=[url],
            ),
        )
        scope_invoke = cog.ResourceServerScope(
            scope_name="invoke", scope_description="Call approved APIs"
        )
        resource = pool.add_resource_server("HubScope", identifier="hub", scopes=[scope_invoke])
        machines = {}
        cog.CfnUserPoolGroup(self, "Auditors", user_pool_id=pool.user_pool_id, group_name="audit")
        for project in projects:
            for group in ("use-", "own-"):
                cog.CfnUserPoolGroup(
                    self, group + project, user_pool_id=pool.user_pool_id, group_name=group + project
                )
            machine = pool.add_client(
                "Machine-" + project,
                generate_secret=True,
                user_pool_client_name="tsugite-" + project,
                o_auth=cog.OAuthSettings(
                    flows=cog.OAuthFlows(client_credentials=True),
                    scopes=[cog.OAuthScope.resource_server(resource, scope_invoke)],
                ),
            )
            machines[machine.user_pool_client_id] = project
        targets = dict(cfg.get("targets", {}))
        if not config_file:
            sample = fn.Function(
                self,
                "Sample",
                runtime=runtime,
                handler="index.handler",
                code=fn.Code.from_inline(
                    'import json\ndef handler(event, context):\n    return {"statusCode":200,"headers":{"content-type":"application/json"},"body":json.dumps({"items":[{"sku":"TS-01","stock":12}]})}'
                ),
            )
            targets["stock-sandbox"] = {
                "owner": "supply",
                "environment": "sandbox",
                "kind": "lambda",
                "address": sample.function_arn,
            }
        for target in targets.values():
            if target["owner"] not in projects or target["environment"] not in ("sandbox", "production"):
                raise ValueError("invalid target owner or environment")
            if target["kind"] == "lambda":
                if "*" in target["address"]:
                    raise ValueError("use a specific Lambda ARN")
                role.add_to_policy(
                    iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[target["address"]])
                )
            elif target["kind"] != "https":
                raise ValueError("unknown target")
            if target.get("secret_arn"):
                if "*" in target["secret_arn"]:
                    raise ValueError("use a specific secret ARN")
                role.add_to_policy(
                    iam.PolicyStatement(
                        actions=["secretsmanager:GetSecretValue"], resources=[target["secret_arn"]]
                    )
                )
        # CloudFormation dynamic values can be used in values, never as JSON keys.
        config = {
            "issuer": pool.user_pool_provider_url,
            "domain": domain.base_url(),
            "portal_client": portal.user_pool_client_id,
            "machine_projects": [
                {"client": client, "project": project} for client, project in machines.items()
            ],
            "targets": targets,
        }
        ssm.StringParameter(
            self, "PortalSettings", parameter_name=param, string_value=self.to_json_string(config)
        )
        CfnOutput(self, "PortalUrl", value=url)
        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "TokenEndpoint", value=domain.base_url() + "/oauth2/token")
