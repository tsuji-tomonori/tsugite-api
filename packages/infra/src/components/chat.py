"""チャット用のLambdaと権限を構成する。"""

import json

from aws_cdk import Aws, Duration, RemovalPolicy, Size
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_logs as logs
from cdk_nag import NagSuppressions
from constructs import Construct

from .functions import EVENT_PYTHON, ROOT


class PortalChat(Construct):
    def __init__(self, scope: Construct, key: str, api, cluster, backend_code, dependencies):
        super().__init__(scope, key)
        jobs = ddb.Table(
            self,
            "Jobs",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires",
            removal_policy=RemovalPolicy.DESTROY,
        )
        NagSuppressions.add_resource_suppressions(
            jobs,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "Temporary chat results expire; recovery is unnecessary.",
                }
            ],
        )
        bucket = f"cdk-hnb659fds-assets-{Aws.ACCOUNT_ID}-{Aws.REGION}"
        artifacts = json.loads((ROOT / "packages/model/src/manifest.json").read_text(encoding="utf-8"))
        role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_to_policy(
            iam.PolicyStatement(actions=["dsql:DbConnect"], resources=[cluster.attr_resource_arn])
        )
        group = self.log_group("Worker")
        worker = fn.Function(
            self,
            "Worker",
            runtime=EVENT_PYTHON,
            handler="chat_jobs.handler",
            code=backend_code,
            layers=[dependencies],
            role=role,
            log_group=group,
            environment={
                "CHAT_TABLE": jobs.table_name,
                "DSQL_HOST": cluster.attr_endpoint,
                "DSQL_USER": "tsugite_chat",
            },
            memory_size=768,
            timeout=Duration.seconds(145),
            retry_attempts=0,
            max_event_age=Duration.minutes(2),
        )
        self.allow_logs(group, role)
        model_layers = {
            name: fn.LayerVersion(
                self,
                construct_id,
                code=fn.Code.from_asset(str(ROOT / "build" / f"{name}-layer.zip")),
                compatible_runtimes=[runtime],
                compatible_architectures=[fn.Architecture.X86_64],
            )
            for name, construct_id, runtime in (
                ("decision-model", "DecisionDependencies", fn.Runtime.PYTHON_3_14),
                ("decision-weights", "DecisionWeights", fn.Runtime.PYTHON_3_14),
                ("model-sdk", "SdkDependencies", EVENT_PYTHON),
            )
        }
        for model, timeout in (("decision", 35), ("tool", 65), ("generate", 65)):
            name = model.title()
            inference_role = iam.Role(
                self, name + "Role", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
            )
            group = self.log_group(name)
            self.allow_logs(group, inference_role)
            inference = fn.Function(
                self,
                name,
                runtime=fn.Runtime.PYTHON_3_14 if model == "decision" else EVENT_PYTHON,
                handler="decision.handler" if model == "decision" else "completion.handler",
                code=fn.Code.from_asset(
                    str(ROOT / "build" / ("chat-decision" if model == "decision" else "chat-llm"))
                ),
                layers=(
                    [model_layers["decision-model"], model_layers["decision-weights"]]
                    if model == "decision"
                    else [model_layers["model-sdk"]]
                ),
                environment={
                    "MODEL_ROLE": model,
                    "TOKENIZERS_PARALLELISM": "false",
                },
                log_group=group,
                role=inference_role,
                memory_size=3008,  # 配備先アカウントの関数あたりの上限（MB）
                ephemeral_storage_size=Size.mebibytes(512),
                timeout=Duration.seconds(timeout),
            )
            if model == "decision":
                NagSuppressions.add_resource_suppressions(
                    inference,
                    [
                        {
                            "id": "AwsSolutions-L1",
                            "reason": "ONNX Runtime has no CPython 3.15 Linux x86_64 wheel.",
                        }
                    ],
                )
            else:
                inference.add_environment("MODEL_BUCKET", bucket)
                inference.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["s3:GetObject"],
                        resources=[
                            f"arn:{Aws.PARTITION}:s3:::{bucket}/tsugite-chat-models/{model}/"
                            f"{item.get('sha256', item['revision'])}/{item['name']}"
                            for item in artifacts[model]
                        ],
                    )
                )
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"], resources=[inference.function_arn]
                )
            )
            worker.add_environment("CHAT_" + model.upper(), inference.function_name)
        for principal, actions in (
            (api, ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]),
            (worker, ["dynamodb:GetItem", "dynamodb:UpdateItem"]),
        ):
            principal.add_to_role_policy(
                iam.PolicyStatement(actions=actions, resources=[jobs.table_arn])
            )
        api.add_to_role_policy(
            iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[worker.function_arn])
        )
        api.add_environment("CHAT_TABLE", jobs.table_name)
        api.add_environment("CHAT_WORKER", worker.function_name)
        self.worker_role = role

    def log_group(self, name):
        return logs.LogGroup(self, name + "Logs", retention=logs.RetentionDays.ONE_MONTH)

    @staticmethod
    def allow_logs(group, role):
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[group.log_group_arn],
            )
        )
