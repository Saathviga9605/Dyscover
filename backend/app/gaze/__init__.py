"""Gaze observation ingestion and deterministic feature extraction (Stage 1).

Gaze is an optional first-class observation modality.  This package owns the
canonical gaze sample/fixation schema, the per-trial ingest boundary, and the
deterministic, non-clinical feature extraction used by the shared feature
architecture.  No inference, no raw video, and no identity-related data ever
enters the system.
"""

from .features import aggregate_gaze_features, analyze_fixations
from .schemas import GazeTrialBatchCreate, GazeStatusResponse

__all__ = ["GazeTrialBatchCreate", "GazeStatusResponse", "analyze_fixations", "aggregate_gaze_features"]