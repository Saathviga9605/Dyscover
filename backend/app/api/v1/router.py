"""API v1 router - aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.auth.routes import router as auth_router
from app.ml.routes import router as ml_router
from app.ml.quality import router as ml_quality_router
from app.personalization.routes import router as personalization_router
from app.remedial.routes import router as remedial_router
from app.speech.routes import router as speech_router
from app.speech.demo_routes import router as speech_demo_router
from app.gaze.routes import router as gaze_router
from app.privacy.routes import router as privacy_router
from app.remedial.routes import router as remedial_router

# Create the v1 router
router = APIRouter(prefix="/v1")

# Include all v1 routers
router.include_router(auth_router, prefix="/auth", tags=["authentication"])
router.include_router(ml_router, prefix="/ml", tags=["ml-research"])
router.include_router(ml_quality_router, prefix="/ml/quality", tags=["ml-quality"])
router.include_router(personalization_router, prefix="/personalization", tags=["personalization"])
router.include_router(remedial_router, prefix="/remedial", tags=["remedial"])
router.include_router(chat.router, prefix="/chat", tags=["lexi-chat"])
router.include_router(speech_router, prefix="/speech", tags=["speech-research"])
router.include_router(speech_demo_router, prefix="/speech/demo", tags=["speech-demo"])
router.include_router(gaze_router, prefix="/gaze", tags=["gaze-research"])
router.include_router(privacy_router, prefix="/privacy", tags=["privacy"])
router.include_router(remedial_router, prefix="/remedial", tags=["remedial"])
router.include_router(chat.router, prefix="/chat", tags=["lexi-chat"])

# Note: The legacy routes (without /v1 prefix) are maintained in main.py for backward compatibility
# but new clients should use the /api/v1/ prefix