# APIの実行環境を構成する。
from aws_cdk import ArnFormat, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct

from .functions import EVENT_PYTHON, catalog_function


class ApiRuntime(Construct):
    def __init__(self, scope: Construct, key: str, cluster, param, code, dependency_code):
        super().__init__(scope, key)
        secret = sm.Secret(
            self, "OriginKey", generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True)
        )
        token_signer = sm.Secret(
            self,
            "TokenSigner",
            generate_secret_string=sm.SecretStringGenerator(
                password_length=64, exclude_punctuation=True
            ),
        )
        role = iam.Role(self, "RuntimeRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        runtime_env = {
            "TOKEN_SIGNING_KEY": token_signer.secret_value.unsafe_unwrap(),
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
                    Stack.of(self).format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name=param.lstrip("/"),
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    )
                ],
            )
        )

        self.dependencies = fn.LayerVersion(
            self,
            "Dependencies",
            code=dependency_code,
            compatible_runtimes=[EVENT_PYTHON],
            compatible_architectures=[fn.Architecture.X86_64],
        )
        self.role = role
        self.origin_secret = secret
        self.api = catalog_function(
            self, "Api", "app.main.handler", runtime_env, code, self.dependencies, role
        )
        archive = s3.Bucket(
            self,
            "Specifications",
            versioned=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
        self.api.add_environment("SPEC_BUCKET", archive.bucket_name)
        role.add_to_policy(
            iam.PolicyStatement(actions=["s3:PutObject"], resources=[archive.arn_for_objects("specs/*")])
        )
        self.authorizer = catalog_function(
            self, "Access", "app.authorizer.handler", runtime_env, code, self.dependencies, role
        )
