"""Authentication, authorization and configuration security tests."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
import base64
import json

import jwt

from app.auth.deps import CSRF_HEADER, CSRF_HEADER_VALUE
from app.auth.routes import REFRESH_COOKIE
from app.auth.utils import ALGORITHM, create_access_token
from app.core.config import ConfigurationError, Settings
from app.core.rate_limit import limiter
from app.main import app
from tests.conftest import TEST_PASSWORD, create_user, token_for
from tests.helpers import trial_payload

CSRF = {CSRF_HEADER: CSRF_HEADER_VALUE}

PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/speech/status"),
    ("GET", "/api/gaze/status"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/logout"),
}


def _login(client: TestClient, email: str, password: str = TEST_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --- every non-public route requires a bearer token -------------------------------

def _api_routes():
    # Enumerated from the OpenAPI schema (stable across FastAPI router internals).
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/"):
            continue
        for method in operations:
            if method.upper() in {"HEAD", "OPTIONS"}:
                continue
            if (method.upper(), path) not in PUBLIC_ROUTES:
                yield method.upper(), path


def test_route_enumeration_is_complete() -> None:
    routes = set(_api_routes())
    assert len(routes) >= 60
    assert ("POST", "/api/chat/conversations/{conversation_id}/messages") in routes
    assert ("DELETE", "/api/privacy/account") in routes


@pytest.mark.parametrize("method,path", sorted(set(_api_routes())))
def test_every_protected_route_rejects_anonymous_requests(anon_client: TestClient, method: str, path: str) -> None:
    concrete = path
    for name in ("child_id", "assessment_id", "trial_id", "game_session_id", "session_id", "speech_session_id", "conversation_id", "educator_id"):
        concrete = concrete.replace("{" + name + "}", str(uuid.uuid4()))
    concrete = concrete.replace("{game_id}", "letter-detective").replace("{activity_id}", "symbol-match").replace("{model_id}", "x")
    response = anon_client.request(method, concrete, json={})
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


# --- tokens ----------------------------------------------------------------------

def test_invalid_expired_and_forged_tokens_are_rejected(anon_client: TestClient) -> None:
    user = create_user()
    expired = create_access_token(user.id, user.role, user.token_version, expires_delta=timedelta(seconds=-5))
    forged = jwt.encode({"sub": str(user.id), "role": "parent", "ver": 0, "type": "access", "iat": 0, "exp": 9999999999}, "wrong-key" * 5, algorithm=ALGORITHM)
    def b64(part: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()

    unsigned = f'{b64({"alg": "none", "typ": "JWT"})}.{b64({"sub": str(user.id), "ver": 0, "type": "access", "iat": 0, "exp": 9999999999})}.'

    wrong_type = jwt.encode({"sub": str(user.id), "ver": 0, "type": "refresh", "iat": 0, "exp": 9999999999}, Settings().secret_key, algorithm=ALGORITHM)
    for token in (expired, forged, unsigned, wrong_type, "not-a-jwt", str(user.id)):
        response = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, token
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_for(user)}"}).status_code == 200


def test_inactive_user_token_is_rejected(anon_client: TestClient) -> None:
    from app.database import SessionLocal
    from app.models import User

    user = create_user()
    token = token_for(user)
    with SessionLocal() as db:
        db.get(User, user.id).is_active = False
        db.commit()
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _login(anon_client, user.email).status_code == 401


# --- registration / login ----------------------------------------------------------

def test_register_login_me_and_no_refresh_token_in_body(anon_client: TestClient) -> None:
    email = f"New.User-{uuid.uuid4().hex[:8]}@Example.com"
    registered = anon_client.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD, "display_name": " Pat "})
    assert registered.status_code == 201
    assert registered.json()["email"] == email.lower()
    assert "password_hash" not in registered.json()
    login = _login(anon_client, email.upper())
    assert login.status_code == 200
    assert "refresh_token" not in login.json()
    assert REFRESH_COOKIE in login.cookies
    set_cookie = login.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "path=/api/auth" in set_cookie
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["display_name"] == "Pat"


def test_registration_rejects_privileged_roles_and_weak_passwords(anon_client: TestClient) -> None:
    base = {"email": f"r-{uuid.uuid4().hex[:8]}@example.com", "display_name": "X"}
    assert anon_client.post("/api/auth/register", json={**base, "password": TEST_PASSWORD, "role": "admin"}).status_code == 422
    assert anon_client.post("/api/auth/register", json={**base, "password": "short"}).status_code == 422
    assert anon_client.post("/api/auth/register", json={**base, "password": "x" * 73}).status_code == 422


def test_login_does_not_reveal_whether_account_exists(anon_client: TestClient) -> None:
    user = create_user()
    wrong_password = _login(anon_client, user.email, "wrong-password-123")
    unknown_user = _login(anon_client, f"ghost-{uuid.uuid4().hex[:8]}@example.com")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_validation_errors_do_not_echo_submitted_values(anon_client: TestClient) -> None:
    response = anon_client.post("/api/auth/register", json={"email": "bad", "password": "secret-value-xyz", "display_name": ""})
    assert response.status_code == 422
    assert "secret-value-xyz" not in response.text


# --- refresh tokens ----------------------------------------------------------------

def test_refresh_rotates_and_detects_reuse(anon_client: TestClient) -> None:
    user = create_user()
    login = _login(anon_client, user.email)
    first_cookie = login.cookies[REFRESH_COOKIE]

    assert anon_client.post("/api/auth/refresh").status_code == 403  # CSRF header missing
    rotated = anon_client.post("/api/auth/refresh", headers=CSRF)
    assert rotated.status_code == 200
    second_cookie = rotated.cookies[REFRESH_COOKIE]
    assert second_cookie != first_cookie

    # Replaying the first (rotated) token revokes the whole family.
    replay = TestClient(app)
    replay.cookies.set(REFRESH_COOKIE, first_cookie, path="/api/auth")
    assert replay.post("/api/auth/refresh", headers=CSRF).status_code == 401
    fresh = TestClient(app)
    fresh.cookies.set(REFRESH_COOKIE, second_cookie, path="/api/auth")
    assert fresh.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_logout_revokes_refresh_token(anon_client: TestClient) -> None:
    user = create_user()
    login = _login(anon_client, user.email)
    cookie = login.cookies[REFRESH_COOKIE]
    assert anon_client.post("/api/auth/logout").status_code == 403
    assert anon_client.post("/api/auth/logout", headers=CSRF).status_code == 204
    other = TestClient(app)
    other.cookies.set(REFRESH_COOKIE, cookie, path="/api/auth")
    assert other.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_password_change_invalidates_other_sessions(anon_client: TestClient) -> None:
    user = create_user()
    old_session = TestClient(app)
    old_login = _login(old_session, user.email)
    old_access = old_login.json()["access_token"]

    changer = TestClient(app)
    access = _login(changer, user.email).json()["access_token"]
    bad = changer.post("/api/auth/change-password", headers={"Authorization": f"Bearer {access}"}, json={"current_password": "nope", "new_password": "another-good-pass"})
    assert bad.status_code == 400
    changed = changer.post("/api/auth/change-password", headers={"Authorization": f"Bearer {access}"}, json={"current_password": TEST_PASSWORD, "new_password": "another-good-pass"})
    assert changed.status_code == 200

    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 401
    assert old_session.post("/api/auth/refresh", headers=CSRF).status_code == 401
    assert changer.get("/api/auth/me", headers={"Authorization": f"Bearer {changed.json()['access_token']}"}).status_code == 200
    assert _login(anon_client, user.email).status_code == 401
    assert _login(anon_client, user.email, "another-good-pass").status_code == 200


def test_logout_all_invalidates_access_tokens(client: TestClient) -> None:
    assert client.post("/api/auth/logout-all").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


# --- rate limiting -------------------------------------------------------------------

def test_login_is_rate_limited(anon_client: TestClient) -> None:
    limiter.reset()
    limiter.enabled = True
    try:
        statuses = [_login(anon_client, "rate-limit@example.com", "wrong-password").status_code for _ in range(12)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert statuses[:10] == [401] * 10
    assert 429 in statuses[10:]


# --- cross-user resource access (IDOR) -------------------------------------------------

def test_other_parent_cannot_read_or_write_child_resources(make_client) -> None:
    owner, intruder = make_client("parent"), make_client("parent")
    child = owner.post("/api/children", json={"display_name": "Ava"}).json()
    assessment = owner.post("/api/assessments", json={"child_id": child["id"]}).json()
    trial = owner.post(f"/api/assessments/{assessment['id']}/games/letter-detective/trials", json=trial_payload("letter-detective", 1, True)).json()
    speech = owner.post("/api/speech/sessions", json={"session_id": assessment["id"], "trial_id": trial["id"], "task": {"task_id": "t", "expected_text": "cat"}}).json()
    practice = owner.post("/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match"}).json()

    reads = [
        f"/api/children/{child['id']}",
        f"/api/children/{child['id']}/assessments",
        f"/api/assessments/{assessment['id']}",
        f"/api/assessments/{assessment['id']}/modality-summary",
        f"/api/trials/{trial['id']}/events",
        f"/api/gaze/trials/{trial['id']}/gaze",
        f"/api/gaze/trials/{trial['id']}/gaze/features",
        f"/api/speech/sessions/{speech['id']}",
        f"/api/speech/sessions/{speech['id']}/features",
        f"/api/ml/profile/session/{assessment['id']}",
        f"/api/ml/features/session/{assessment['id']}",
        f"/api/personalization/children/{child['id']}/profile",
        f"/api/personalization/children/{child['id']}/recommendations",
        f"/api/personalization/children/{child['id']}/progress",
        f"/api/remedial/children/{child['id']}/next-activity",
        f"/api/remedial/children/{child['id']}/practice/progress",
    ]
    for path in reads:
        assert intruder.get(path).status_code == 404, path
        assert owner.get(path).status_code == 200, path

    writes = [
        ("post", "/api/assessments", {"child_id": child["id"]}),
        ("post", f"/api/assessments/{assessment['id']}/games/letter-detective/trials", trial_payload("letter-detective", 2, True)),
        ("post", f"/api/trials/{trial['id']}/events", {"event_type": "TRIAL_STARTED"}),
        ("post", f"/api/gaze/trials/{trial['id']}/gaze", {"samples": [], "fixations": []}),
        ("post", f"/api/speech/sessions/{speech['id']}/features", {"features": {}}),
        ("post", "/api/speech/sessions", {"session_id": assessment["id"], "task": {"task_id": "t", "expected_text": "cat"}}),
        ("post", f"/api/assessments/{assessment['id']}/summary", {"games": [], "total_trials": 0}),
        ("post", "/api/remedial/sessions", {"child_id": child["id"], "activity_id": "symbol-match"}),
        ("post", f"/api/remedial/sessions/{practice['id']}/start", None),
        ("post", f"/api/remedial/sessions/{practice['id']}/abandon", None),
        ("patch", f"/api/children/{child['id']}", {"display_name": "Hacked"}),
        ("delete", f"/api/children/{child['id']}", None),
    ]
    for method, path, body in writes:
        response = intruder.request(method.upper(), path, json=body)
        assert response.status_code == 404, f"{method} {path} -> {response.status_code}"
    assert owner.get(f"/api/children/{child['id']}").json()["display_name"] == "Ava"
    assert intruder.get("/api/children").json() == []


def test_speech_session_cannot_link_a_foreign_trial(make_client) -> None:
    owner, other = make_client("parent"), make_client("parent")
    other_child = other.post("/api/children", json={"display_name": "B"}).json()
    other_assessment = other.post("/api/assessments", json={"child_id": other_child["id"]}).json()
    foreign_trial = other.post(f"/api/assessments/{other_assessment['id']}/games/letter-detective/trials", json=trial_payload("letter-detective", 1, True)).json()
    child = owner.post("/api/children", json={"display_name": "A"}).json()
    assessment = owner.post("/api/assessments", json={"child_id": child["id"]}).json()
    response = owner.post("/api/speech/sessions", json={"session_id": assessment["id"], "trial_id": foreign_trial["id"], "task": {"task_id": "t", "expected_text": "cat"}})
    assert response.status_code == 404


def test_educators_cannot_create_children(make_client) -> None:
    assert make_client("educator").post("/api/children", json={"display_name": "X"}).status_code == 403


# --- configuration -------------------------------------------------------------------

@pytest.mark.parametrize("secret", ["", "changeme", "changeme-in-production", "short-secret"])
def test_production_refuses_insecure_secret_keys(secret: str, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises((ConfigurationError, ValueError)):
        Settings(_env_file=None)


def test_production_accepts_strong_secret_and_rejects_wildcard_cors(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 48)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    settings = Settings(_env_file=None)
    assert settings.cookie_secure is True and settings.should_auto_migrate is False
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises((ConfigurationError, ValueError)):
        Settings(_env_file=None)


def test_security_headers_and_request_id(anon_client: TestClient) -> None:
    response = anon_client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    injected = anon_client.get("/api/health", headers={"X-Request-ID": "bad\nvalue with spaces"})
    assert injected.headers["X-Request-ID"] != "bad\nvalue with spaces"


def test_oversized_json_body_is_rejected(client: TestClient) -> None:
    response = client.post("/api/children", content=b"{" + b" " * (3 * 1024 * 1024) + b"}", headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_cors_allows_configured_origin_with_credentials(anon_client: TestClient) -> None:
    preflight = anon_client.options(
        "/api/auth/refresh",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": CSRF_HEADER},
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-credentials"] == "true"
    evil = anon_client.options("/api/auth/refresh", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers
