"""Alembic migrations produce exactly the ORM schema and survive downgrade/upgrade."""

from __future__ import annotations

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core.migrations import alembic_config, head_revision
from app.database import Base


def _fresh_url() -> str:
    return f"sqlite:///{(Path(tempfile.mkdtemp()) / 'migrate.db').as_posix()}"


def test_fresh_upgrade_matches_models_exactly() -> None:
    url = _fresh_url()
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert context.get_current_revision() == head_revision(url)
        assert compare_metadata(context, Base.metadata) == []
    engine.dispose()


def test_downgrade_to_baseline_and_back() -> None:
    url = _fresh_url()
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "1c08bf9c22ca")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert "conversations" not in tables and "refresh_tokens" not in tables and "trials" in tables
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert {"conversations", "messages", "refresh_tokens"} <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_legacy_create_all_database_upgrades_without_data_loss() -> None:
    """Databases built by the old ``create_all`` startup path and stamped at the
    baseline must upgrade in place, keeping their rows."""
    url = _fresh_url()
    config = alembic_config(url)
    command.upgrade(config, "1c08bf9c22ca")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO users (id, email, role, is_active, created_at) VALUES ('00000000000000000000000000000001', 'legacy@example.com', 'parent', 1, '2026-01-01')")
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT email, token_version FROM users").one()
    assert row == ("legacy@example.com", 0)
    engine.dispose()
