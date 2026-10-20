"""Shared test fixtures.

Every test session runs against a throw-away SQLite database created through the
real Alembic migrations (never ``dyscover.db``). Environment variables are set
before any ``app`` import so the engine binds to the temporary database.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="dyscover-tests-"))
os.environ["APP_ENV"] = "test"
# TEST_DATABASE_URL lets the suite run against an empty PostgreSQL database.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-" + "x" * 32
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ.pop("DYSCOVER_ASR_PROVIDER", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.utils as auth_utils  # noqa: E402

auth_utils.BCRYPT_ROUNDS = 4  # fast hashing for tests only

from app.auth.utils import create_access_token, hash_password  # noqa: E402
from app.chat import service as chat_service  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.speech.provider import reset_speech_providers  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def _migrated_app():
    # Entering the client runs the lifespan, which applies all migrations.
    with TestClient(app):
        yield


@pytest.fixture(autouse=True)
def _reset_global_state():
    reset_speech_providers()
    chat_service.set_provider(None)
    yield
    reset_speech_providers()
    chat_service.set_provider(None)


def create_user(role: str = "parent", email: str | None = None, password: str = TEST_PASSWORD, display_name: str | None = None) -> User:
    with SessionLocal() as db:
        user = User(
            email=email or f"{role}-{uuid.uuid4().hex[:12]}@example.com",
            display_name=display_name or role.title(),
            role=role,
            is_active=True,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def token_for(user: User) -> str:
    return create_access_token(user.id, user.role, user.token_version)


def authed_client(user: User) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token_for(user)}"
    client.user = user  # type: ignore[attr-defined]
    return client


@pytest.fixture
def make_client():
    """Factory: ``make_client("educator")`` -> TestClient authenticated as a new user."""
    clients: list[TestClient] = []

    def factory(role: str = "parent", **kwargs) -> TestClient:
        client = authed_client(create_user(role, **kwargs))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client) -> TestClient:
    """A TestClient authenticated as a fresh parent account."""
    return make_client("parent")


@pytest.fixture
def anon_client():
    with TestClient(app) as test_client:
        yield test_client
