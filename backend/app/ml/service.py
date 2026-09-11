from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AssessmentSession, GameSession, InteractionEvent, SessionFeatureVector, Trial
from . import FEATURE_EXTRACTOR_VERSION, FEATURE_SCHEMA_VERSION
from .features import extract_session_features
from .profile import build_profile


def session_data(db: Session, session_id: UUID):
    session = db.get(AssessmentSession, session_id)
    if session is None: return None
    games = list(db.scalars(select(GameSession).where(GameSession.assessment_session_id == session_id)))
    game_ids = [game.id for game in games]
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_ids)))) if game_ids else []
    trial_ids = [trial.id for trial in trials]
    events = list(db.scalars(select(InteractionEvent).where(InteractionEvent.trial_id.in_(trial_ids)))) if trial_ids else []
    return session, games, trials, events


def extract_profile(db: Session, session_id: UUID):
    data = session_data(db, session_id)
    if data is None: return None
    session, games, trials, events = data
    features, quality = extract_session_features(session, games, trials, events)
    stored = db.scalar(select(SessionFeatureVector).where(SessionFeatureVector.assessment_id == session_id))
    serialized = {name: value for name, value in features.items()}
    if stored is None:
        db.add(SessionFeatureVector(assessment_id=session_id, feature_schema_version=FEATURE_SCHEMA_VERSION, feature_extractor_version=FEATURE_EXTRACTOR_VERSION, features=serialized, quality=quality))
    else:
        stored.features = serialized
        stored.quality = quality
    db.commit()
    return features, quality, build_profile(str(session_id), features, quality)
