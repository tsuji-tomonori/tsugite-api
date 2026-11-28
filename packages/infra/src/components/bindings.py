"""上流APIの接続設定を構成する。"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from .functions import EVENT_PYTHON, ROOT


class UpstreamBindings(Construct):
    def __init__(self, scope: Construct, key: str, cfg, include_sample, projects, identity, role, param):
        super().__init__(scope, key)
        targets = dict(cfg.get("targets", {}))
        if include_sample:
            for environment, name in (
                ("sandbox", "Sample"),
                ("staging", "StagingSample"),
                ("production", "ProductionSample"),
            ):
                sample = fn.Function(
                    self,
                    name,
                    runtime=EVENT_PYTHON,
                    handler="sample_api.main.handler",
                    code=fn.Code.from_asset(str(ROOT / "build/sample-api")),
                    memory_size=256,
                    timeout=Duration.seconds(10),
                )
                targets["stock-" + environment] = {
                    "owner": "supply",
                    "environment": environment,
                    "kind": "lambda",
                    "address": sample.function_arn,
                }
        for target in targets.values():
            if target["owner"] not in projects or target["environment"] not in (
                "sandbox",
                "staging",
                "production",
            ):
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
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:ListUsers",
                    "cognito-idp:ListUsersInGroup",
                ],
                resources=[identity.pool.user_pool_arn],
            )
        )
        config = {
            "pool_id": identity.pool.user_pool_id,
            "projects": projects,
            "issuer": identity.pool.user_pool_provider_url,
            "domain": identity.domain.base_url(),
            "portal_client": identity.client.user_pool_client_id,
            "machine_projects": identity.machines,
            "targets": targets,
        }
        ssm.StringParameter(
            self,
            "PortalSettings",
            parameter_name=param,
            string_value=Stack.of(self).to_json_string(config),
        )
