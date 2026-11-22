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
    def __init__(self, scope: Construct, key: str, api, cluster, backend_code):
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
        artifacts = json.loads((ROOT / "agent/models/manifest.json").read_text(encoding="utf-8"))
        role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_to_policy(
            iam.PolicyStatement(actions=["dsql:DbConnect"], resources=[cluster.attr_resource_arn])
        )
        group = self.log_group("Worker")
        worker = fn.Function(
            self,
            "Worker",
            runtime=EVENT_PYTHON,
            handler="agent.jobs.handler",
            code=backend_code,
            role=role,
            log_group=group,
            environment={
                "CHAT_TABLE": jobs.table_name,
                "DSQL_HOST": cluster.attr_endpoint,
                "DSQL_USER": "tsugite_chat",
            },
            memory_size=768,
            timeout=Duration.seconds(145),
            reserved_concurrent_executions=4,
            retry_attempts=0,
            max_event_age=Duration.minutes(2),
        )
        self.allow_logs(group, role)
        for model, memory, timeout in (
            ("decision", 3072, 35),
            ("tool", 4096, 65),
            ("generate", 4096, 65),
        ):
            name = model.title()
            inference_role = iam.Role(
                self, name + "Role", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
            )
            group = self.log_group(name)
            self.allow_logs(group, inference_role)
            inference = fn.Function(
                self,
                name,
                runtime=fn.Runtime.PYTHON_3_14,
                handler="decision.handler" if model == "decision" else "completion.handler",
                code=fn.Code.from_asset(
                    str(ROOT / "build" / ("chat-decision" if model == "decision" else "chat-llm"))
                ),
                environment={
                    "MODEL_BUCKET": bucket,
                    "MODEL_ROLE": model,
                    "TOKENIZERS_PARALLELISM": "false",
                },
                log_group=group,
                role=inference_role,
                memory_size=memory,
                ephemeral_storage_size=Size.mebibytes(512),
                timeout=Duration.seconds(timeout),
                reserved_concurrent_executions=4,
            )
            NagSuppressions.add_resource_suppressions(
                inference,
                [
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "Native inference packages target the stable Python 3.14 Lambda runtime.",
                    }
                ],
            )
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
