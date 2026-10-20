"""Structured audit logging for security-relevant operations.

Audit records identify actors and resources by opaque IDs only. Callers pass short
machine-readable reason codes as ``error_message`` — never emails, passwords,
tokens, child names, transcripts or exception text.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

logger = logging.getLogger("dyscover.audit")

_MAX_REASON_LENGTH = 64


class AuditEventType:
    """Standard audit event types."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_PASSWORD_CHANGE = "user_password_change"
    CHILD_CREATE = "child_create"
    CHILD_UPDATE = "child_update"
    CHILD_DELETE = "child_delete"
    ASSESSMENT_CREATE = "assessment_create"
    ASSESSMENT_COMPLETE = "assessment_complete"
    TRIAL_SUBMIT = "trial_submit"
    EDUCATOR_AUTHORIZE = "educator_authorize"
    EDUCATOR_REVOKE = "educator_revoke"
    SPEECH_SESSION_CREATE = "speech_session_create"
    SPEECH_TRANSCRIBE = "speech_transcribe"
    GAZE_DATA_UPLOAD = "gaze_data_upload"
    PRACTICE_SESSION_START = "practice_session_start"
    PRACTICE_SESSION_COMPLETE = "practice_session_complete"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    PERMISSION_CHANGE = "permission_change"
    CONFIG_CHANGE = "config_change"
    ACCESS_DENIED = "access_denied"


def _reason(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:_MAX_REASON_LENGTH]


def log_audit_event(
    event_type: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    audit_data: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "success": success,
        "reason": _reason(error_message),
    }
    if request is not None:
        audit_data["ip"] = request.client.host if request.client else None
        audit_data["request_id"] = getattr(request.state, "request_id", None)
    logger.info(json.dumps(audit_data, default=str))


class AuditLogger:
    """Request-bound convenience wrapper around :func:`log_audit_event`."""

    def __init__(self, request: Request | None = None):
        self.request = request

    def log(
        self,
        event_type: str,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        log_audit_event(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            request=self.request,
            success=success,
            error_message=error_message,
        )
