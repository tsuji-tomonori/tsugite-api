from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text

from app.db.session import engine


def test_schema_matches_models_and_replays(portal):
    from app.db.models import Base
    cfg=Config("backend/alembic.ini")
    db=engine()
    schema=inspect(db)
    for table in Base.metadata.sorted_tables:
        assert {col["name"] for col in schema.get_columns(table.name)} == set(table.columns.keys())
    command.downgrade(cfg,"base")
    command.upgrade(cfg,"001")
    with db.begin() as conn:
        conn.execute(text("INSERT INTO assets (id,owner,name,summary,spec,targets,published,revision) VALUES (:id,:owner,:name,:summary,:spec,:targets,:published,1)"),dict(id="before",owner="p",name="旧版",summary="用途",spec="{}",targets="{}",published=False))
    command.upgrade(cfg,"head")
    with db.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version"))=="002"
        assert conn.execute(text("select name,base_path from assets where id='before'")).one()==("旧版",None)
