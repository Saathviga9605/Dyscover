"""Privacy export and deletion behaviour."""

from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.chat import service as chat_service
from app.database import SessionLocal
from app.models import (
    AssessmentSession,
    AssessmentSummary,
    ChildProfile,
    Conversation,
    EducatorLearnerAssignment,
    GazeSample,
    InteractionEvent,
    Message,
    PracticeEvent,
    PracticeSession,
    RefreshToken,
    SessionFeatureVector,
    SpeechSession,
    Trial,
    User,
)
from tests.conftest import TEST_PASSWORD
from tests.helpers import trial_payload


class EchoProvider:
    name = "fake"
    model = "fake-model"

    def complete(self, messages):
        return "Hello from the test provider."


def _populate(client: TestClient, educator: TestClient) -> dict:
    child = client.post("/api/children", json={"display_name": "Ava", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    trial = client.post(f"/api/assessments/{assessment['id']}/games/letter-detective/trials", json=trial_payload("letter-detective", 1, True)).json()
    client.post(f"/api/trials/{trial['id']}/events", json={"event_type": "TRIAL_STARTED", "sequence_number": 1})
    client.post(f"/api/gaze/trials/{trial['id']}/gaze", json={"samples": [{"x": 1, "y": 1, "timestamp_ms": 5}], "fixations": [{"start_timestamp_ms": 5, "end_timestamp_ms": 10, "duration_ms": 5, "x": 1, "y": 1}], "calibration_completed": True})
    speech = client.post("/api/speech/sessions", json={"session_id": assessment["id"], "trial_id": trial["id"], "task": {"task_id": "t", "expected_text": "cat"}}).json()
    client.post(f"/api/speech/sessions/{speech['id']}/features", json={"features": {"speech_speech_detected": {"value": 1, "available": True}}})
    client.get(f"/api/ml/features/session/{assessment['id']}")  # persists a SessionFeatureVector
    client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 1})
    practice = client.post("/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match"}).json()
    client.post(f"/api/remedial/sessions/{practice['id']}/start")
    client.post(f"/api/remedial/sessions/{practice['id']}/events", json={"event_type": "ITEM_PRESENTED", "payload": {}})
    client.post(f"/api/children/{child['id']}/educators", json={"educator_email": educator.user.email})
    chat_service.set_provider(EchoProvider())
    conversation = client.post("/api/chat/conversations", json={}).json()
    client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Hi Lexi"})
    return {"child": child, "assessment": assessment, "trial": trial}


def test_export_contains_own_data_and_never_credentials(make_client) -> None:
    owner, other, educator = make_client("parent"), make_client("parent"), make_client("educator")
    _populate(owner, educator)
    other.post("/api/children", json={"display_name": "Someone Else"})

    response = owner.get("/api/privacy/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    raw = archive.read("user_data.json").decode("utf-8")
    data = json.loads(raw)
    assert "password_hash" not in raw and "token_hash" not in raw and "token_version" not in raw
    assert data["user"]["email"] == owner.user.email
    assert [child["display_name"] for child in data["children"]] == ["Ava"]
    child = data["children"][0]
    trial = child["assessments"][0]["game_sessions"][0]["trials"][0]
    assert trial["events"] and trial["gaze_samples"] and trial["fixations"]
    assert child["assessments"][0]["speech_sessions"]
    assert child["practice_sessions"][0]["events"]
    assert child["educator_access"][0]["status"] == "active"
    assert data["lexi_conversations"][0]["messages"][0]["content"] == "Hi Lexi"
    assert "Someone Else" not in raw


def _counts(user_id, child_id) -> dict[str, int]:
    child_id = UUID(str(child_id))
    with SessionLocal() as db:
        def count(model, *where):
            return db.scalar(select(func.count()).select_from(model).where(*where))

        assessment_ids = select(AssessmentSession.id).where(AssessmentSession.child_id == child_id)
        return {
            "users": count(User, User.id == user_id),
            "children": count(ChildProfile, ChildProfile.id == child_id),
            "assessments": count(AssessmentSession, AssessmentSession.child_id == child_id),
            "summaries": count(AssessmentSummary, AssessmentSummary.assessment_id.in_(assessment_ids)),
            "session_features": count(SessionFeatureVector, SessionFeatureVector.assessment_id.in_(assessment_ids)),
            "events": count(InteractionEvent, InteractionEvent.session_id.in_(assessment_ids)),
            "speech": count(SpeechSession, SpeechSession.assessment_id.in_(assessment_ids)),
            "practice": count(PracticeSession, PracticeSession.child_id == child_id),
            "assignments": count(EducatorLearnerAssignment, EducatorLearnerAssignment.child_id == child_id),
            "conversations": count(Conversation, Conversation.user_id == user_id),
            "refresh_tokens": count(RefreshToken, RefreshToken.user_id == user_id),
        }


def test_account_deletion_requires_password_and_removes_everything(make_client) -> None:
    owner, educator = make_client("parent"), make_client("educator")
    created = _populate(owner, educator)
    owner.post("/api/auth/login", json={"email": owner.user.email, "password": TEST_PASSWORD})  # creates a refresh token row
    before = _counts(owner.user.id, created["child"]["id"])
    assert all(value >= 1 for value in before.values()), before

    assert owner.request("DELETE", "/api/privacy/account", json={"password": "wrong"}).status_code == 400
    assert _counts(owner.user.id, created["child"]["id"]) == before

    assert owner.request("DELETE", "/api/privacy/account", json={"password": TEST_PASSWORD}).status_code == 204
    after = _counts(owner.user.id, created["child"]["id"])
    assert all(value == 0 for value in after.values()), after
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Trial).where(Trial.id == UUID(created["trial"]["id"]))) == 0
        assert db.scalar(select(func.count()).select_from(GazeSample).where(GazeSample.trial_id == UUID(created["trial"]["id"]))) == 0
    # The token of a deleted account is useless; the educator no longer sees the learner.
    assert owner.get("/api/auth/me").status_code == 401
    assert educator.get("/api/educator/learners").json() == []


def test_child_deletion_removes_only_that_child(make_client) -> None:
    owner, educator = make_client("parent"), make_client("educator")
    created = _populate(owner, educator)
    sibling = owner.post("/api/children", json={"display_name": "Sibling"}).json()
    assert owner.delete(f"/api/children/{created['child']['id']}").status_code == 204
    counts = _counts(owner.user.id, created["child"]["id"])
    assert counts["children"] == counts["assessments"] == counts["practice"] == counts["speech"] == counts["summaries"] == 0
    assert counts["users"] == 1 and counts["conversations"] == 1
    assert [child["id"] for child in owner.get("/api/children").json()] == [sibling["id"]]


def test_data_summary_counts_only_own_records(make_client) -> None:
    owner, educator, other = make_client("parent"), make_client("educator"), make_client("parent")
    _populate(owner, educator)
    other.post("/api/children", json={"display_name": "Else"})
    summary = owner.get("/api/privacy/data-summary").json()
    assert summary["children"]["count"] == 1
    assert summary["assessments"]["count"] == 1
    assert summary["trials"]["count"] == 1
    assert summary["practice_sessions"]["count"] == 1
    assert summary["lexi_conversations"]["count"] == 1
    assert "password" not in json.dumps(summary)
