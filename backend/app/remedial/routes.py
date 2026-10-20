"""Remedial practice API surface (minimal).

Endpoints:
- ``GET  /api/remedial/activities``               catalog (age-filterable)
- ``GET  /api/remedial/children/{child_id}/next-activity``
- ``POST /api/remedial/sessions``                 create (planned)
- ``POST /api/remedial/sessions/{id}/start``
- ``POST /api/remedial/sessions/{id}/events``     structured practice event
- ``POST /api/remedial/sessions/{id}/complete``
- ``POST /api/remedial/sessions/{id}/abandon``
- ``GET  /api/remedial/children/{child_id}/practice/progress``

Errors are explicit states: unknown child/activity, unknown session, invalid
session state (409), invalid event type (400).
"""

import uuid

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import get_child_for_user, get_practice_session_for_user
from ..auth.deps import get_current_user
from ..database import get_db
from ..models import ChildProfile, User
from ..personalization.service import build_child_profile, build_game_difficulty
from . import catalog, content
from .progress import build_practice_progress
from .recommend import get_child_age, select_activity
from .session import (
    SessionError,
    abandon_session,
    complete_session,
    create_practice_session,
    practice_history,
    record_event,
    start_session,
)

router = APIRouter(prefix="/api/remedial", tags=["remedial-practice"])


class CreatePracticeSessionRequest(BaseModel):
    child_id: uuid.UUID
    activity_id: str = Field(min_length=1, max_length=80)
    # Out-of-range values are clamped by the session service (documented contract).
    difficulty: int | None = Field(default=None, ge=-100, le=100)
    language: str = Field(default="en", max_length=16)


class RecordEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict)


def _raise(error: SessionError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.message)


def _require_child(db: Session, user: User, child_id: uuid.UUID, allow_educator: bool = False) -> ChildProfile:
    return get_child_for_user(db, user, child_id, allow_educator=allow_educator)


@router.get("/activities")
def list_activities(child_id: uuid.UUID | None = None, age: int | None = Query(default=None, ge=3, le=18), capabilities: str | None = None, language: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resolved_age = age
    capability_filter = tuple(capabilities.split(",")) if capabilities else None
    if child_id is not None:
        child = _require_child(db, user, child_id, allow_educator=True)
        resolved_age = get_child_age({"birth_year": child.birth_year})
    return [activity.to_dict() for activity in catalog.available_activities(age=resolved_age, capabilities=capability_filter, language=language)]


@router.get("/activities/{activity_id}/speech-tasks")
def speech_tasks_for(activity_id: str, count: int = Query(default=5, ge=1, le=20), seed: int = Query(default=0, ge=0), language: str = "en", _: User = Depends(get_current_user)):
    tasks = content.speech_tasks(activity_id, count=count, seed=seed, language=language)
    if not tasks:
        raise HTTPException(status_code=404, detail="No curated speech content available for this activity and language.")
    return {"activity_id": activity_id, "content_version": content.CONTENT_VERSION, "language": language, "tasks": tasks}


@router.get("/children/{child_id}/next-activity")
def next_activity(child_id: uuid.UUID, capabilities: str | None = None, language: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = _require_child(db, user, child_id, allow_educator=True)
    profile = build_child_profile(db, str(child_id))
    history = practice_history(db, child_id)
    age = get_child_age({"birth_year": child.birth_year})

    def _difficulty(db_: Session, child: str, game_id: str):
        return build_game_difficulty(db_, child, game_id)

    capability_filter = tuple(capabilities.split(",")) if capabilities else ("pointer",)
    recommendation = select_activity(
        profile,
        history,
        age=age,
        difficulty_service=_difficulty,
        db=db,
        child_id=str(child_id),
        capabilities=capability_filter,
        language=language,
    )
    return {
        "child_id": str(child_id),
        "kind": recommendation["kind"],
        "activity": recommendation["activity"],
        "target_domain": recommendation["target_domain"],
        "target_domain_label": recommendation["target_domain_label"],
        "difficulty_level": recommendation["difficulty_level"],
        "difficulty_previous_level": recommendation["difficulty_previous_level"],
        "reason": recommendation["reason"],
        "recommendation_version": recommendation["recommendation_version"],
        "content_version": recommendation["content_version"],
        "language": recommendation.get("language"),
    }


@router.post("/sessions", status_code=201)
def create_session(payload: CreatePracticeSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_child(db, user, payload.child_id)
    try:
        session = create_practice_session(db, payload.child_id, payload.activity_id, payload.difficulty, language=payload.language)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/start")
def start(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_practice_session_for_user(db, user, session_id)
    try:
        session = start_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/events", status_code=201)
def record(session_id: uuid.UUID, payload: RecordEventRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_practice_session_for_user(db, user, session_id)
    try:
        event = record_event(db, session_id, payload.event_type, payload.payload)
    except SessionError as error:
        _raise(error)
    return {
        "id": str(event.id),
        "practice_session_id": str(event.practice_session_id),
        "mode": event.mode,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "sequence_number": event.sequence_number,
        "schema_version": event.schema_version,
        "payload": event.payload,
    }


@router.post("/sessions/{session_id}/complete")
def complete(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_practice_session_for_user(db, user, session_id)
    try:
        session = complete_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/abandon")
def abandon(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_practice_session_for_user(db, user, session_id)
    try:
        session = abandon_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.get("/children/{child_id}/practice/progress")
def practice_progress(child_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_child(db, user, child_id, allow_educator=True)
    return build_practice_progress(db, child_id)


def _session_dict(session) -> dict:
    return {
        "id": str(session.id),
        "child_id": str(session.child_id),
        "mode": session.mode,
        "activity_id": session.activity_id,
        "target_domain": session.target_domain,
        "difficulty": session.difficulty,
        "activity_version": session.activity_version,
        "content_version": session.content_version,
        "language": session.language,
        "config_version": session.config_version,
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "metadata": session.metadata_json or {},
    }