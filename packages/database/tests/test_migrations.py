from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from tsugite_db.session import engine


def test_schema_matches_models_and_replays(tmp_path, monkeypatch):
    """DB定義がモデルと一致し、旧版のデータを移行できる"""
    from tsugite_db.models import Base

    cfg = Config("packages/database/alembic.ini")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "migration.db"))
    engine.cache_clear()
    command.upgrade(cfg, "head")
    db = engine()
    schema = inspect(db)
    for table in Base.metadata.sorted_tables:
        assert {col["name"] for col in schema.get_columns(table.name)} == set(table.columns.keys())
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "001")
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO assets (id,owner,name,summary,spec,targets,published,revision) VALUES (:id,:owner,:name,:summary,:spec,:targets,:published,1)"
            ),
            dict(
                id="before",
                owner="p",
                name="旧版",
                summary="用途",
                spec="{}",
                targets="{}",
                published=False,
            ),
        )
    command.upgrade(cfg, "004")
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO api_keys (id,digest,project,creator,name,kind,scopes,revoked,revision) "
                "VALUES ('old-key','existing-digest','finance','reader','既存キー','shared','[]',false,1)"
            )
        )
    command.upgrade(cfg, "head")
    with db.connect() as conn:
        legacy = conn.execute(text("SELECT mode,created,digest FROM api_keys WHERE id='old-key'")).one()
        assert legacy.mode is None and legacy.created > 0 and legacy.digest == "existing-digest"
        assert conn.scalar(text("select version_num from alembic_version")) == "007"
        assert conn.execute(text("select name,base_path from assets where id='before'")).one() == (
            "旧版",
            None,
        )
    db.dispose()
    engine.cache_clear()
