"""Demo endpoints for speech transcription and model comparison."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.speech.provider import get_speech_provider
from app.speech.schemas import ProviderState, SpeechStatusResponse, Transcript

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speech/demo", tags=["speech-demo"])

# In-memory storage for demo uploads (in production, use proper storage)
DEMO_UPLOAD_DIR = Path("data/demo_audio")
DEMO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".webm"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB


def validate_audio_file(file: UploadFile) -> list[str]:
    """Validate uploaded audio file."""
    errors = []

    # Check file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file format: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Check content type
    if file.content_type and not file.content_type.startswith("audio/"):
        errors.append(f"Invalid content type: {file.content_type}")

    return errors


@router.get("/providers")
def list_available_providers() -> dict[str, Any]:
    """List all available speech providers and their status."""
    import os

    providers = {
        "unconfigured": {"name": "unconfigured", "available": True},
        "huggingface-whisper": {
            "name": "huggingface-whisper",
            "available": bool(os.getenv("DYSCOVER_HF_WHISPER_MODEL", "").strip()),
            "model": os.getenv("DYSCOVER_HF_WHISPER_MODEL", "openai/whisper-tiny"),
            "language": os.getenv("DYSCOVER_HF_WHISPER_LANGUAGE", "en"),
            "device": os.getenv("DYSCOVER_HF_WHISPER_DEVICE", "auto"),
        },
        "faster-whisper": {
            "name": "faster-whisper",
            "available": bool(os.getenv("DYSCOVER_ASR_MODEL", "").strip()),
            "model": os.getenv("DYSCOVER_ASR_MODEL", "small"),
            "model_path": os.getenv("DYSCOVER_ASR_MODEL_PATH", ""),
            "device": os.getenv("DYSCOVER_ASR_DEVICE", "cpu"),
        },
    }

    # Check current provider status
    current_provider = get_speech_provider()
    health = current_provider.health_check()

    return {
        "current_provider": current_provider.name,
        "current_provider_status": health.value,
        "providers": providers,
    }


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    provider: str | None = Form(None),
    consent: bool = Form(False),
) -> dict[str, Any]:
    """
    Transcribe uploaded audio file using configured speech provider.
    
    Requires explicit consent for processing child audio.
    """
    # Validate file
    errors = validate_audio_file(file)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Check consent
    if not consent:
        raise HTTPException(
            status_code=403,
            detail="Explicit consent is required for audio processing. Set consent=true.",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    # Save to temporary file
    ext = Path(file.filename or "audio.wav").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".wav"

    temp_id = uuid.uuid4().hex[:8]
    temp_path = DEMO_UPLOAD_DIR / f"demo_{temp_id}{ext}"
    temp_path.write_bytes(content)

    try:
        # Get provider
        if provider:
            # Temporarily override provider
            import os
            old_provider = os.getenv("DYSCOVER_ASR_PROVIDER")
            os.environ["DYSCOVER_ASR_PROVIDER"] = provider
            speech_provider = get_speech_provider()
            if old_provider:
                os.environ["DYSCOVER_ASR_PROVIDER"] = old_provider
            else:
                os.environ.pop("DYSCOVER_ASR_PROVIDER", None)
        else:
            speech_provider = get_speech_provider()

        # Check provider status
        health = speech_provider.health_check()
        if health == ProviderState.NOT_CONFIGURED:
            raise HTTPException(
                status_code=503,
                detail="No speech provider configured. Set DYSCOVER_ASR_PROVIDER=huggingface-whisper or faster-whisper",
            )
        if health == ProviderState.UNAVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Configured speech provider is unavailable",
            )

        # Transcribe
        transcript = speech_provider.transcribe(
            audio_reference=str(temp_path),
            language=language,
            consent_given=True,
        )

        return {
            "transcript": transcript.model_dump(),
            "provider": speech_provider.name,
            "provider_version": speech_provider.version,
            "audio_info": {
                "filename": file.filename,
                "size_bytes": len(content),
                "duration_estimated": len(content) / 32000,  # rough estimate for 16kHz mono
            },
        }

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")
    finally:
        # Clean up temp file
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.post("/compare")
async def compare_models(
    file: UploadFile = File(...),
    language: str = Form("en"),
    consent: bool = Form(False),
) -> dict[str, Any]:
    """
    Compare transcription from multiple available providers on the same audio.
    """
    errors = validate_audio_file(file)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    if not consent:
        raise HTTPException(
            status_code=403,
            detail="Explicit consent is required for audio processing.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    ext = Path(file.filename or "audio.wav").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".wav"

    temp_id = uuid.uuid4().hex[:8]
    temp_path = DEMO_UPLOAD_DIR / f"demo_compare_{temp_id}{ext}"
    temp_path.write_bytes(content)

    try:
        import os

        results = {}
        providers_to_try = []

        # Check which providers are available
        hf_model = os.getenv("DYSCOVER_HF_WHISPER_MODEL", "").strip()
        if hf_model:
            providers_to_try.append(("huggingface-whisper", "huggingface-whisper"))

        fw_model = os.getenv("DYSCOVER_ASR_MODEL", "").strip()
        if fw_model:
            providers_to_try.append(("faster-whisper", "faster-whisper"))

        if not providers_to_try:
            raise HTTPException(
                status_code=503,
                detail="No speech providers configured for comparison",
            )

        for provider_name, env_value in providers_to_try:
            old_provider = os.getenv("DYSCOVER_ASR_PROVIDER")
            os.environ["DYSCOVER_ASR_PROVIDER"] = env_value
            try:
                speech_provider = get_speech_provider()
                health = speech_provider.health_check()
                if health != ProviderState.AVAILABLE:
                    results[provider_name] = {
                        "status": "unavailable",
                        "error": f"Provider health check failed: {health.value}",
                    }
                    continue

                transcript = speech_provider.transcribe(
                    audio_reference=str(temp_path),
                    language=language,
                    consent_given=True,
                )
                results[provider_name] = {
                    "status": "success",
                    "transcript": transcript.model_dump(),
                    "provider_version": speech_provider.version,
                }
            except Exception as e:
                results[provider_name] = {
                    "status": "error",
                    "error": str(e),
                }
            finally:
                if old_provider:
                    os.environ["DYSCOVER_ASR_PROVIDER"] = old_provider
                else:
                    os.environ.pop("DYSCOVER_ASR_PROVIDER", None)

        return {
            "audio_info": {
                "filename": file.filename,
                "size_bytes": len(content),
            },
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail="Comparison failed")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.get("/models")
def list_configured_models() -> dict[str, Any]:
    """List all configured models from environment."""
    import os

    return {
        "huggingface_whisper": {
            "model": os.getenv("DYSCOVER_HF_WHISPER_MODEL", "openai/whisper-tiny"),
            "language": os.getenv("DYSCOVER_HF_WHISPER_LANGUAGE", "en"),
            "device": os.getenv("DYSCOVER_HF_WHISPER_DEVICE", "auto"),
            "dtype": os.getenv("DYSCOVER_HF_WHISPER_DTYPE", "float32"),
            "cache_dir": os.getenv("DYSCOVER_HF_WHISPER_CACHE", ""),
        },
        "faster_whisper": {
            "model": os.getenv("DYSCOVER_ASR_MODEL", "small"),
            "model_path": os.getenv("DYSCOVER_ASR_MODEL_PATH", ""),
            "device": os.getenv("DYSCOVER_ASR_DEVICE", "cpu"),
            "compute_type": os.getenv("DYSCOVER_ASR_COMPUTE_TYPE", "int8"),
        },
    }