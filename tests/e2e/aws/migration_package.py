"""Run the packaged migration using the DSQL dialect and a local PostgreSQL socket."""

import os
import sys
from importlib import import_module
from pathlib import Path


def main():
    asset = Path(sys.argv[1]).resolve()
    layer = Path(sys.argv[2]).resolve()
    socket_dir, expected_revision = sys.argv[3:]
    sys.path[:0] = [str(asset), str(layer)]
    os.environ["LAMBDA_TASK_ROOT"] = str(asset)

    import psycopg
    from sqlalchemy import create_engine, event, text
    from tsugite_db import session

    assert Path(psycopg.__file__).is_relative_to(layer)
    assert Path(session.__file__).is_relative_to(asset)

    # Load the production connector's dependencies even though the wire endpoint is local.
    import_module("aurora_dsql_psycopg")
    database = create_engine(
        "auroradsql+psycopg://",
        creator=lambda: psycopg.connect(host=socket_dir, user="admin", dbname="postgres"),
    )
    session.engine = lambda: database

    from app.migrate import handler

    role_arn = "arn:aws:iam::000000000000:role/tsugite-runtime"
    chat_arn = "arn:aws:iam::000000000000:role/tsugite-chat"
    roles = {"RuntimeRoleArn": role_arn, "ChatRoleArn": chat_arn}
    iam_grants = []

    @event.listens_for(database, "before_cursor_execute", retval=True)
    def apply_dsql_permissions(_conn, _cursor, statement, parameters, _context, _executemany):
        sql = " ".join(statement.upper().split())
        if sql.startswith(("GRANT ", "REVOKE ")) and " ON SCHEMA PUBLIC " in sql:
            raise psycopg.errors.FeatureNotSupported("feature not supported on system entity")
        if statement.startswith("AWS IAM GRANT "):
            iam_grants.append(statement)
            return "SELECT 1", parameters
        return statement, parameters

    try:
        for request_type in ("Create", "Update"):
            result = handler({"RequestType": request_type, "ResourceProperties": roles}, None)
            assert result["PhysicalResourceId"] == "tsugite-catalog-schema"
        assert (
            iam_grants
            == [
                f"AWS IAM GRANT tsugite_app TO '{role_arn}'",
                f"AWS IAM GRANT tsugite_chat TO '{chat_arn}'",
            ]
            * 2
        )
        with database.connect() as connection:
            assert list(connection.scalars(text("SELECT version_num FROM alembic_version"))) == [
                expected_revision
            ]
            connection.exec_driver_sql("SET ROLE tsugite_app")
            assert connection.scalar(text("SELECT current_user")) == "tsugite_app"
            assert connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'USAGE')")
            )
            assert connection.scalar(
                text("SELECT has_table_privilege(current_user, 'assets', 'INSERT')")
            )
            assert connection.scalar(
                text("SELECT has_table_privilege(current_user, 'audit_events', 'INSERT')")
            )
            assert not connection.scalar(
                text("SELECT has_table_privilege(current_user, 'audit_events', 'UPDATE')")
            )
            assert list(connection.execute(text("SELECT base_path, offers FROM assets")).keys()) == [
                "base_path",
                "offers",
            ]
            connection.execute(text("SELECT subject, question, answer FROM inquiries LIMIT 0"))
            connection.exec_driver_sql("RESET ROLE")
            connection.exec_driver_sql("SET ROLE tsugite_chat")
            connection.execute(text("SELECT id, name FROM assets LIMIT 0"))
            assert not connection.scalar(
                text("SELECT has_table_privilege(current_user, 'assets', 'INSERT')")
            )
            assert not connection.scalar(
                text("SELECT has_table_privilege(current_user, 'inquiries', 'SELECT')")
            )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
