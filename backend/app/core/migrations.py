"""Programmatic Alembic helpers used at startup and in tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def head_revision(database_url: str) -> str | None:
    return ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_to_head(engine: Engine) -> None:
    command.upgrade(alembic_config(engine.url.render_as_string(hide_password=False)), "head")


def ensure_schema_current(engine: Engine, auto_migrate: bool) -> None:
    """Upgrade (development) or verify (production) that the schema is at head."""
    url = engine.url.render_as_string(hide_password=False)
    if auto_migrate:
        upgrade_to_head(engine)
        return
    current, head = current_revision(engine), head_revision(url)
    if current != head:
        raise RuntimeError(
            f"Database schema is at revision {current!r} but the application requires {head!r}. "
            "Run `alembic upgrade head` before starting the API."
        )
