import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import get_trial_for_user
from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Fixation, GazeSample, InteractionEvent, User
from .features import analyze_fixations
from .schemas import (
    GAZE_SCHEMA_VERSION,
    GazeBatchResponse,
    GazeStatusResponse,
    GazeTrialBatchCreate,
    GazeTrialSummary,
)

router = APIRouter(prefix="/api/gaze", tags=["gaze-research"])

_EPOCH_SECONDS = 1_000.0


def _to_utc(timestamp_ms: float) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / _EPOCH_SECONDS, tz=timezone.utc).replace(tzinfo=None)


def _to_epoch_ms(value: datetime) -> float:
    return value.replace(tzinfo=timezone.utc).timestamp() * _EPOCH_SECONDS


def _sanitize_samples(payload: GazeTrialBatchCreate) -> tuple[list[GazeSample], int]:
    samples: list[GazeSample] = []
    rejected = 0
    previous: float | None = None
    for incoming in payload.samples:
        x, y = float(incoming.x), float(incoming.y)
        if not math.isfinite(x) or not math.isfinite(y) or x < 0 or y < 0:
            rejected += 1
            continue
        if incoming.viewport_width and x > incoming.viewport_width + 10:
            rejected += 1
            continue
        if incoming.viewport_height and y > incoming.viewport_height + 10:
            rejected += 1
            continue
        quality = incoming.quality
        if previous is not None and incoming.timestamp_ms < previous:
            quality = "out_of_order"
        previous = max(previous, incoming.timestamp_ms) if previous is not None else incoming.timestamp_ms
        samples.append(
            GazeSample(
                timestamp=_to_utc(incoming.timestamp_ms),
                x=x,
                y=y,
                confidence=incoming.confidence,
                quality=quality,
                provider=payload.provider,
                viewport_width=incoming.viewport_width,
                viewport_height=incoming.viewport_height,
            )
        )
    return samples, rejected


def _sanitize_fixations(payload: GazeTrialBatchCreate) -> tuple[list[Fixation], int]:
    fixations: list[Fixation] = []
    rejected = 0
    for incoming in payload.fixations:
        x, y = float(incoming.x), float(incoming.y)
        if not math.isfinite(x) or not math.isfinite(y) or x < 0 or y < 0 or incoming.end_timestamp_ms < incoming.start_timestamp_ms:
            rejected += 1
            continue
        fixations.append(
            Fixation(
                start_time=_to_utc(incoming.start_timestamp_ms),
                end_time=_to_utc(incoming.end_timestamp_ms),
                duration_ms=incoming.duration_ms,
                x=x,
                y=y,
                target_type=incoming.target_type,
                target_id=incoming.target_id,
            )
        )
    return fixations, rejected


@router.get("/status", response_model=GazeStatusResponse)
def gaze_status() -> GazeStatusResponse:
    return GazeStatusResponse(sample_schema_version=GAZE_SCHEMA_VERSION)


@router.post("/trials/{trial_id}/gaze", response_model=GazeBatchResponse, status_code=status.HTTP_201_CREATED)
def ingest_trial_gaze(trial_id: UUID, payload: GazeTrialBatchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GazeBatchResponse:
    trial_id = get_trial_for_user(db, user, trial_id).id
    samples, samples_rejected = _sanitize_samples(payload)
    fixations, fixations_rejected = _sanitize_fixations(payload)
    # Retried batches (offline queue) must not duplicate observations.
    seen_samples = set(db.scalars(select(GazeSample.timestamp).where(GazeSample.trial_id == trial_id)))
    seen_fixations = set(db.scalars(select(Fixation.start_time).where(Fixation.trial_id == trial_id)))
    samples = [sample for sample in samples if sample.timestamp not in seen_samples]
    fixations = [fixation for fixation in fixations if fixation.start_time not in seen_fixations]
    for sample in samples:
        sample.trial_id = trial_id
    for fixation in fixations:
        fixation.trial_id = trial_id
    finalized = "degraded" if (samples_rejected or fixations_rejected or any(sample.quality in {"degraded", "out_of_order"} for sample in samples)) else payload.quality
    db.add_all(samples)
    db.add_all(fixations)
    if payload.calibration_completed:
        existing = db.scalar(
            select(InteractionEvent.id).where(
                InteractionEvent.trial_id == trial_id,
                InteractionEvent.event_type == "CALIBRATION_COMPLETED",
            )
        )
        if existing is None:
            db.add(
                InteractionEvent(
                    trial_id=trial_id,
                    event_type="CALIBRATION_COMPLETED",
                    payload={"provider": payload.provider, "provider_version": payload.provider_version},
                    schema_version="1.0",
                )
            )
    db.commit()
    return GazeBatchResponse(
        trial_id=trial_id,
        samples_created=len(samples),
        fixations_created=len(fixations),
        samples_rejected=samples_rejected,
        fixations_rejected=fixations_rejected,
        quality=finalized,
    )


@router.get("/trials/{trial_id}/gaze", response_model=GazeTrialSummary)
def trial_gaze(trial_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GazeTrialSummary:
    trial_id = get_trial_for_user(db, user, trial_id).id
    samples = list(db.scalars(select(GazeSample).where(GazeSample.trial_id == trial_id)))
    fixations = list(db.scalars(select(Fixation).where(Fixation.trial_id == trial_id)))
    if not samples and not fixations:
        quality = None  # nothing recorded: unknown, not "tracking"
    else:
        quality = "degraded" if any(sample.quality in {"degraded", "out_of_order"} for sample in samples) else "tracking"
    return GazeTrialSummary(
        trial_id=trial_id,
        sample_count=len(samples),
        fixation_count=len(fixations),
        quality=quality,
        fixations=[
            {
                "start_timestamp_ms": _to_epoch_ms(fixation.start_time),
                "end_timestamp_ms": _to_epoch_ms(fixation.end_time),
                "duration_ms": fixation.duration_ms,
                "x": fixation.x,
                "y": fixation.y,
                "target_type": fixation.target_type,
                "target_id": fixation.target_id,
            }
            for fixation in fixations
        ],
    )


@router.get("/trials/{trial_id}/gaze/features")
def trial_gaze_features(trial_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    trial_id = get_trial_for_user(db, user, trial_id).id
    samples = list(db.scalars(select(GazeSample).where(GazeSample.trial_id == trial_id)))
    fixations = list(db.scalars(select(Fixation).where(Fixation.trial_id == trial_id)))
    normalized = [
        {
            "start_epoch_ms": _to_epoch_ms(fixation.start_time),
            "end_epoch_ms": _to_epoch_ms(fixation.end_time),
            "duration_ms": fixation.duration_ms,
            "x": fixation.x,
            "y": fixation.y,
            "target_type": fixation.target_type,
        }
        for fixation in fixations
    ]
    return {"trial_id": str(trial_id), "gaze_available": bool(samples or fixations), "features": analyze_fixations(len(samples), normalized)}