# ポータルの認証基盤を構成する。
import hashlib
import re

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_cognito as cog
from constructs import Construct


class PortalIdentity(Construct):
    def __init__(self, scope: Construct, key: str, projects, url):
        super().__init__(scope, key)
        pool = cog.UserPool(
            self,
            "Default",
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
                + Stack.of(self).account
                + "-"
                + Stack.of(self).region
                + "-"
                + hashlib.sha256(Stack.of(self).stack_name.encode()).hexdigest()[:6]
            ),
        )
        portal = pool.add_client(
            "WebClient",
            generate_secret=False,
            auth_flows=cog.AuthFlow(user_password=True, user_srp=True),
            prevent_user_existence_errors=True,
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

        def group(name, logical_id):
            resource = cog.CfnUserPoolGroup(
                self, logical_id, user_pool_id=pool.user_pool_id, group_name=name
            )
            resource.override_logical_id(re.sub("[^A-Za-z0-9]", "", logical_id))

        group("admin", "PortalAdmins")
        group("audit", "Auditors")
        for project in projects:
            for prefix in ("use-", "own-"):
                group(prefix + project, prefix + project)
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
        self.pool = pool
        self.domain = domain
        self.client = portal
        self.machines = [{"client": client, "project": project} for client, project in machines.items()]
