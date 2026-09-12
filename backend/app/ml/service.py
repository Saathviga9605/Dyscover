from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AssessmentSession, Fixation, GazeSample, GameSession, InteractionEvent, SessionFeatureVector, SpeechSession, Trial
from . import FEATURE_EXTRACTOR_VERSION, FEATURE_SCHEMA_VERSION
from .features import extract_session_features
from .profile import build_profile
from app.gaze.features import aggregate_gaze_features, analyze_fixations


def _epoch_ms(value) -> float:
    from datetime import timezone

    return value.replace(tzinfo=timezone.utc).timestamp() * 1000


def session_data(db: Session, session_id: UUID):
    session = db.get(AssessmentSession, session_id)
    if session is None: return None
    games = list(db.scalars(select(GameSession).where(GameSession.assessment_session_id == session_id)))
    game_ids = [game.id for game in games]
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_ids)))) if game_ids else []
    trial_ids = [trial.id for trial in trials]
    events = list(db.scalars(select(InteractionEvent).where(InteractionEvent.trial_id.in_(trial_ids)))) if trial_ids else []
    return session, games, trials, events


def _gaze_feature_batches(db: Session, trial_ids: list[UUID]) -> list[dict]:
    samples = list(db.scalars(select(GazeSample).where(GazeSample.trial_id.in_(trial_ids)))) if trial_ids else []
    fixations = list(db.scalars(select(Fixation).where(Fixation.trial_id.in_(trial_ids)))) if trial_ids else []
    by_trial: dict[UUID, dict] = {}
    for sample in samples:
        by_trial.setdefault(sample.trial_id, {"samples": 0, "fixations": []})["samples"] += 1
    for fixation in fixations:
        by_trial.setdefault(fixation.trial_id, {"samples": 0, "fixations": []})["fixations"].append(
            {
                "start_epoch_ms": _epoch_ms(fixation.start_time),
                "end_epoch_ms": _epoch_ms(fixation.end_time),
                "duration_ms": fixation.duration_ms,
                "x": fixation.x,
                "y": fixation.y,
                "target_type": fixation.target_type,
            }
        )
    return [analyze_fixations(entry["samples"], entry["fixations"]) for entry in by_trial.values()]


def _speech_sessions(db: Session, session_id: UUID) -> list[dict]:
    rows = list(db.scalars(select(SpeechSession).where(SpeechSession.assessment_id == session_id)))
    return [{"speech_session_id": row.id, "features": row.features_json or {}, "language": row.language} for row in rows]


def extract_profile(db: Session, session_id: UUID):
    data = session_data(db, session_id)
    if data is None: return None
    session, games, trials, events = data
    trial_ids = [trial.id for trial in trials]
    gaze_features = aggregate_gaze_features(_gaze_feature_batches(db, trial_ids))
    speech_sessions = _speech_sessions(db, session_id)
    features, quality = extract_session_features(session, games, trials, events, gaze_features=gaze_features, speech_sessions=speech_sessions)
    stored = db.scalar(select(SessionFeatureVector).where(SessionFeatureVector.assessment_id == session_id))
    serialized = {name: value for name, value in features.items()}
    if stored is None:
        db.add(SessionFeatureVector(assessment_id=session_id, feature_schema_version=FEATURE_SCHEMA_VERSION, feature_extractor_version=FEATURE_EXTRACTOR_VERSION, features=serialized, quality=quality))
    else:
        stored.features = serialized
        stored.quality = quality
    db.commit()
    return features, quality, build_profile(str(session_id), features, quality, language=session.language, locale=session.locale)
