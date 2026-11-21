"""CloudFormation provider. Delete retains catalog data and audit history."""
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.session import engine


def handler(event,context):
    result={"PhysicalResourceId":"tsugite-catalog-schema"}
    if event["RequestType"]=="Delete":
        return result
    root=Path(os.getenv("LAMBDA_TASK_ROOT","."))
    command.upgrade(Config(str(root/"alembic.ini")),"head")
    arn=event["ResourceProperties"]["RuntimeRoleArn"]
    if not re.fullmatch(r"arn:[a-z0-9-]+:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+",arn):
        raise ValueError("Invalid IAM role")
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='tsugite_app'")):
            conn.exec_driver_sql("CREATE ROLE tsugite_app WITH LOGIN")
        conn.exec_driver_sql(f"AWS IAM GRANT tsugite_app TO '{arn}'")
        conn.exec_driver_sql("GRANT USAGE ON SCHEMA public TO tsugite_app")
        conn.exec_driver_sql("GRANT SELECT, INSERT, UPDATE ON assets, access_rights TO tsugite_app")
        conn.exec_driver_sql("GRANT SELECT, INSERT ON audit_events TO tsugite_app")
    return result
