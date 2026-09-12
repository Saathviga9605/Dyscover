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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChildProfile
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
    activity_id: str
    difficulty: int | None = None


class RecordEventRequest(BaseModel):
    event_type: str
    payload: dict = {}


def _raise(error: SessionError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.message)


def _require_child(db: Session, child_id: uuid.UUID) -> ChildProfile:
    child = db.execute(select(ChildProfile).where(ChildProfile.id == child_id)).scalar_one_or_none()
    if child is None:
        raise HTTPException(status_code=404, detail="Unknown child.")
    return child


@router.get("/activities")
def list_activities(child_id: uuid.UUID | None = None, age: int | None = None, capabilities: str | None = None, db: Session = Depends(get_db)):
    resolved_age = age
    capability_filter = tuple(capabilities.split(",")) if capabilities else None
    if child_id is not None:
        child = _require_child(db, child_id)
        resolved_age = get_child_age({"birth_year": child.birth_year})
    return [activity.to_dict() for activity in catalog.available_activities(age=resolved_age, capabilities=capability_filter)]


@router.get("/activities/{activity_id}/speech-tasks")
def speech_tasks_for(activity_id: str, count: int = 5, seed: int = 0):
    tasks = content.speech_tasks(activity_id, count=count, seed=seed)
    if not tasks:
        raise HTTPException(status_code=404, detail="Unknown speech activity.")
    return {"activity_id": activity_id, "content_version": content.CONTENT_VERSION, "tasks": tasks}


@router.get("/children/{child_id}/next-activity")
def next_activity(child_id: uuid.UUID, capabilities: str | None = None, db: Session = Depends(get_db)):
    child = _require_child(db, child_id)
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
    }


@router.post("/sessions", status_code=201)
def create_session(payload: CreatePracticeSessionRequest, db: Session = Depends(get_db)):
    _require_child(db, payload.child_id)
    try:
        session = create_practice_session(db, payload.child_id, payload.activity_id, payload.difficulty)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/start")
def start(session_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        session = start_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/events", status_code=201)
def record(session_id: uuid.UUID, payload: RecordEventRequest, db: Session = Depends(get_db)):
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
def complete(session_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        session = complete_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.post("/sessions/{session_id}/abandon")
def abandon(session_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        session = abandon_session(db, session_id)
    except SessionError as error:
        _raise(error)
    return _session_dict(session)


@router.get("/children/{child_id}/practice/progress")
def practice_progress(child_id: uuid.UUID, db: Session = Depends(get_db)):
    _require_child(db, child_id)
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
        "config_version": session.config_version,
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "metadata": session.metadata_json or {},
    }