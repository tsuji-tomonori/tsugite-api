from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class UpstreamBindings(Construct):
    def __init__(self, scope: Construct, key: str, cfg, include_sample, projects, identity, role, param):
        super().__init__(scope, key)
        targets = dict(cfg.get("targets", {}))
        if include_sample:
            sample = fn.Function(
                self,
                "Sample",
                runtime=fn.Runtime.PYTHON_3_14,
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
