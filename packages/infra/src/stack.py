"""カタログのCDKスタックを組み立てる。"""

import json
import re
import tomllib
from pathlib import Path

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_lambda as fn
from constructs import Construct

from .components.bindings import UpstreamBindings
from .components.chat import PortalChat
from .components.database import CatalogDatabase
from .components.delivery import PortalDelivery
from .components.functions import ROOT
from .components.gateway import CatalogGateway
from .components.identity import PortalIdentity
from .components.ownership import CatalogSynthesizer, preserve_logical_ids
from .components.runtime import ApiRuntime


class CatalogStack(Stack):
    def __init__(self, scope: Construct, key: str, **kwargs):
        super().__init__(scope, key, synthesizer=CatalogSynthesizer(), **kwargs)
        self.tags.set_tag("Component", "Stack")
        self.tags.set_tag("Application", "TsugiteAPI")
        self.tags.set_tag("ManagedBy", "AWS-CDK")
        prefix = tomllib.loads((ROOT / "deploy/config/http.toml").read_text())["api_prefix"]
        config_file = self.node.try_get_context("bindings")
        cfg = json.loads(Path(config_file).read_text()) if config_file else {}
        projects = cfg.get("projects", ["supply", "finance"])
        if not projects or len(set(projects)) != len(projects):
            raise ValueError("projects must contain unique project names")

        if any(not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", p) for p in projects):
            raise ValueError("invalid project name")
        param = "/" + self.stack_name + "/portal"
        code = fn.Code.from_asset(str(ROOT / "build/lambda"))
        dependency_code = fn.Code.from_asset(str(ROOT / "build/runtime-layer.zip"))
        database = CatalogDatabase(self, "Database")
        runtime = ApiRuntime(self, "Runtime", database.cluster, param, code, dependency_code)
        chat = PortalChat(self, "Chat", runtime.api, database.cluster, code, runtime.dependencies)
        schema = database.install_schema(runtime.role, code, runtime.dependencies, chat.worker_role)
        schema.node.add_dependency(chat)
        runtime.api.node.add_dependency(schema)
        runtime.authorizer.node.add_dependency(schema)
        gateway = CatalogGateway(self, "Gateway", prefix, runtime.api, runtime.authorizer)
        delivery = PortalDelivery(self, "Portal", prefix, gateway.api, runtime.origin_secret)
        identity = PortalIdentity(self, "Identities", projects, delivery.url)
        UpstreamBindings(self, "Bindings", cfg, not config_file, projects, identity, runtime.role, param)
        preserve_logical_ids(self)
        CfnOutput(self, "GatewayEndpoint", value=gateway.api.api_endpoint)
        CfnOutput(self, "PortalUrl", value=delivery.url)
        CfnOutput(self, "UserPoolId", value=identity.pool.user_pool_id)
        CfnOutput(self, "TokenEndpoint", value=identity.domain.base_url() + "/oauth2/token")
