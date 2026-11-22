"""Run the packaged migration using the DSQL dialect and a local PostgreSQL socket."""

import os
import sys
from importlib import import_module
from pathlib import Path


def main():
    asset = Path(sys.argv[1]).resolve()
    socket_dir = sys.argv[2]
    sys.path.insert(0, str(asset))
    os.environ["LAMBDA_TASK_ROOT"] = str(asset)

    import psycopg
    from sqlalchemy import create_engine, event, text
    from tsugite_db import session

    # Load the production connector's dependencies even though the wire endpoint is local.
    import_module("aurora_dsql_psycopg")
    database = create_engine(
        "auroradsql+psycopg://",
        creator=lambda: psycopg.connect(host=socket_dir, user="admin", dbname="postgres"),
    )
    session.engine = lambda: database

    from app.migrate import handler

    role_arn = "arn:aws:iam::000000000000:role/tsugite-runtime"
    iam_grants = []

    @event.listens_for(database, "before_cursor_execute", retval=True)
    def replace_iam_grant(_conn, _cursor, statement, parameters, _context, _executemany):
        if statement.startswith("AWS IAM GRANT "):
            iam_grants.append(statement)
            return "SELECT 1", parameters
        return statement, parameters

    try:
        for request_type in ("Create", "Update"):
            result = handler(
                {"RequestType": request_type, "ResourceProperties": {"RuntimeRoleArn": role_arn}},
                None,
            )
            assert result["PhysicalResourceId"] == "tsugite-catalog-schema"
        assert iam_grants == [f"AWS IAM GRANT tsugite_app TO '{role_arn}'"] * 2
        with database.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006"
            privileges = text("SELECT has_table_privilege('tsugite_app', 'assets', 'INSERT')")
            assert connection.scalar(privileges)
            assert list(connection.execute(text("SELECT base_path, offers FROM assets")).keys()) == [
                "base_path",
                "offers",
            ]
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
