"""CloudFormation provider. Delete retains catalog data and audit history."""

import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from tsugite_db.session import engine

from app.core.diagnostics import emit


def handler(event, context):
    try:
        return migrate(event)
    except Exception as exc:
        emit(
            "schema.migration_failed",
            source="migration",
            failed=True,
            operation=event.get("RequestType"),
            request_id=event.get("RequestId") or getattr(context, "aws_request_id", None),
            reason=type(exc).__name__,
        )
        raise


def migrate(event):
    result = {"PhysicalResourceId": "tsugite-catalog-schema"}
    if event["RequestType"] == "Delete":
        return result
    root = Path(os.getenv("LAMBDA_TASK_ROOT", "."))
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    arn = event["ResourceProperties"]["RuntimeRoleArn"]
    chat_arn = event["ResourceProperties"].get("ChatRoleArn")
    role_pattern = r"arn:[a-z0-9-]+:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+"
    if not re.fullmatch(role_pattern, arn) or (chat_arn and not re.fullmatch(role_pattern, chat_arn)):
        raise ValueError("Invalid IAM role")
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='tsugite_app'")):
            conn.exec_driver_sql("CREATE ROLE tsugite_app WITH LOGIN")
        conn.exec_driver_sql(f"AWS IAM GRANT tsugite_app TO '{arn}'")
        # DSQL protects the public schema, and its USAGE is inherited through PUBLIC.
        conn.exec_driver_sql(
            "GRANT SELECT, INSERT, UPDATE ON assets, access_rights, portal_members, alert_rules, directory_tree, affiliations, api_keys, credential_leases, credential_rules, inquiries TO tsugite_app"
        )
        conn.exec_driver_sql(
            "GRANT SELECT, INSERT ON spec_releases, audit_events, invocation_logs, notices, notice_reads, invocation_units, asset_routes TO tsugite_app"
        )
        conn.exec_driver_sql("GRANT SELECT, INSERT, UPDATE ON portal_member_profiles TO tsugite_app")
        if chat_arn:
            if not conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='tsugite_chat'")):
                conn.exec_driver_sql("CREATE ROLE tsugite_chat WITH LOGIN")
            conn.exec_driver_sql(f"AWS IAM GRANT tsugite_chat TO '{chat_arn}'")
            conn.exec_driver_sql("GRANT SELECT ON assets, asset_routes TO tsugite_chat")
    return result
