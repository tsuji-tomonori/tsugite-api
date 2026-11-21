import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


@lru_cache
def engine() -> Engine:
    if host := os.getenv("DSQL_HOST"):
        from aurora_dsql_sqlalchemy import create_dsql_engine

        return create_dsql_engine(host=host, user=os.environ["DSQL_USER"], pool_size=2, max_overflow=1)
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        raise RuntimeError("DSQL_HOST is required")
    return create_engine(os.getenv("DATABASE_URL", "sqlite:///tsugite.db"))


def session() -> Iterator[Session]:
    with Session(engine(), expire_on_commit=False) as db:
        yield db
