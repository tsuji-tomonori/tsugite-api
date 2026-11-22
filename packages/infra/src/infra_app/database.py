import hashlib

from aws_cdk import CustomResource, RemovalPolicy
from aws_cdk import aws_dsql as dsql
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from .functions import ROOT, catalog_function


class CatalogDatabase(Construct):
    def __init__(self, scope: Construct, key: str):
        super().__init__(scope, key)
        self.cluster = dsql.CfnCluster(self, "Default", deletion_protection_enabled=True)
        self.cluster.apply_removal_policy(RemovalPolicy.RETAIN)

    def install_schema(self, role, code):
        migration = catalog_function(
            self,
            "Migration",
            "app.migrate.handler",
            {"DSQL_HOST": self.cluster.attr_endpoint, "DSQL_USER": "admin"},
            code,
        )
        migration.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dsql:DbConnectAdmin"], resources=[self.cluster.attr_resource_arn]
            )
        )
        provider = cr.Provider(self, "SchemaProvider", on_event_handler=migration)
        digest = hashlib.sha256()
        for path in sorted((ROOT / "packages/database/migrations").rglob("*.py")):
            digest.update(path.read_bytes())
        digest.update((ROOT / "packages/backend/src/app/migrate.py").read_bytes())
        CustomResource(
            self,
            "Schema",
            service_token=provider.service_token,
            properties={"Revision": digest.hexdigest(), "RuntimeRoleArn": role.role_arn},
        )
