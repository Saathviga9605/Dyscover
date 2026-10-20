"""Speech transcription demo endpoints (authenticated adults only).

Uploaded audio is written to a private temporary file, transcribed by a locally
configured provider, and deleted immediately — it is never stored. No audio is
sent to any third-party service by these endpoints.
"""


import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.auth.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.models import User
from app.speech.provider import KNOWN_PROVIDERS, SUPPORTED_ASR_LANGUAGES, SpeechProvider, get_speech_provider
from app.speech.schemas import ProviderState


logger = logging.getLogger("dyscover.speech.demo")

router = APIRouter(prefix="/api/speech/demo", tags=["speech-demo"])

ALLOWED_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".webm"}
_CHUNK = 64 * 1024
# Concurrent transcriptions are CPU/GPU heavy; bound them per process.
_transcription_slots = asyncio.Semaphore(2)


def _validate_upload(file: UploadFile, language: str) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if file.content_type and not (file.content_type.startswith("audio/") or file.content_type in {"application/octet-stream", "video/webm"}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not audio")
    if language not in SUPPORTED_ASR_LANGUAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported language {language!r}")
    return ext


async def _spool_to_tempfile(file: UploadFile, ext: str) -> tuple[Path, int]:
    """Copy the upload to a private temp file, enforcing the size limit while reading."""
    limit = get_settings().speech_upload_max_bytes
    fd, name = tempfile.mkstemp(prefix="dyscover-audio-", suffix=ext)
    path = Path(name)
    size = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            while chunk := await file.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Audio file too large (max {limit // (1024 * 1024)} MB)")
                handle.write(chunk)
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is empty")
    except BaseException:
        _cleanup(path)
        raise
    return path, size


async def _transcribe(provider: SpeechProvider, path: Path, language: str):
    timeout = get_settings().speech_transcription_timeout_seconds
    async with _transcription_slots:
        return await asyncio.wait_for(
            run_in_threadpool(provider.transcribe, audio_reference=str(path), language=language, consent_given=True),
            timeout=timeout,
        )


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:  # still held open by a timed-out worker (Windows)
        logger.warning("Temporary audio file could not be removed immediately")


def _require_consent(consent: bool) -> None:
    if not consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Explicit consent is required before audio is processed")


@router.get("/providers")
def list_available_providers(_: User = Depends(get_current_user)) -> dict[str, Any]:
    current = get_speech_provider()
    return {
        "current_provider": current.name,
        "current_provider_status": current.health_check().value,
        "providers": {name: {"name": name, "status": get_speech_provider(name).health_check().value} for name in KNOWN_PROVIDERS},
    }


@router.post("/transcribe")
@limiter.limit("10/minute")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en"),
    provider: str | None = Form(None),
    consent: bool = Form(False),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_consent(consent)
    ext = _validate_upload(file, language)
    if provider is not None and provider not in KNOWN_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown provider {provider!r}")
    speech_provider = get_speech_provider(provider)
    health = speech_provider.health_check()
    if health != ProviderState.AVAILABLE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Speech provider is not available ({health.value})")

    path, size = await _spool_to_tempfile(file, ext)
    try:
        transcript = await _transcribe(speech_provider, path, language)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Transcription timed out")
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The audio could not be processed")
    except RuntimeError:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Transcription failed")
    finally:
        _cleanup(path)
    return {
        "transcript": transcript.model_dump(),
        "provider": speech_provider.name,
        "provider_version": speech_provider.version,
        "audio_info": {"size_bytes": size, "stored": False},
    }


@router.post("/compare")
@limiter.limit("5/minute")
async def compare_models(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en"),
    consent: bool = Form(False),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_consent(consent)
    ext = _validate_upload(file, language)
    available = [(name, get_speech_provider(name)) for name in KNOWN_PROVIDERS]
    available = [(name, provider) for name, provider in available if provider.health_check() == ProviderState.AVAILABLE]
    if not available:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No speech providers are available for comparison")

    path, size = await _spool_to_tempfile(file, ext)
    results: dict[str, Any] = {}
    try:
        for name, provider in available:
            try:
                transcript = await _transcribe(provider, path, language)
                results[name] = {"status": "success", "transcript": transcript.model_dump(), "provider_version": provider.version}
            except asyncio.TimeoutError:
                results[name] = {"status": "error", "error": "timeout"}
            except Exception:  # one provider failing must not hide the others
                logger.exception("Provider %s failed during comparison", name)
                results[name] = {"status": "error", "error": "transcription_failed"}
    finally:
        _cleanup(path)
    return {"audio_info": {"size_bytes": size, "stored": False}, "results": results}


@router.get("/models")
def list_configured_models(_: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "huggingface_whisper": {
            "model": os.getenv("DYSCOVER_HF_WHISPER_MODEL", ""),
            "device": os.getenv("DYSCOVER_HF_WHISPER_DEVICE", "auto"),
            "status": get_speech_provider("huggingface-whisper").health_check().value,
        },
        "faster_whisper": {
            "model": os.getenv("DYSCOVER_ASR_MODEL", ""),
            "device": os.getenv("DYSCOVER_ASR_DEVICE", "cpu"),
            "status": get_speech_provider("faster-whisper").health_check().value,
        },
    }
