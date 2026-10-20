"""Audit logging for sensitive operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

logger = logging.getLogger("dyscover.audit")


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
    """Log an audit event with structured data."""
    audit_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "success": success,
        "error_message": error_message,
    }

    if request:
        audit_data["ip"] = request.client.host if request.client else None
        audit_data["user_agent"] = request.headers.get("user-agent")
        audit_data["request_id"] = getattr(request.state, "request_id", None)

    # Log as structured JSON for easy parsing
    logger.info(json.dumps(audit_data))


def audit_log(event_type: str, resource_type: str = None, get_resource_id: Callable[[Any], str] = None):
    """Decorator to automatically log audit events for route handlers."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            # Get current user if available
            user_id = None
            try:
                from app.auth.routes import get_current_user_optional
                from app.database import get_db
                from fastapi import Depends

                # This is a simplified approach - in practice, you'd get the user from the request state
                if request and hasattr(request.state, "user"):
                    user_id = str(request.state.user.id) if request.state.user else None
            except Exception:
                pass

            start_time = datetime.now(timezone.utc)
            success = False
            error_message = None
            result = None

            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_message = str(e)
                raise
            finally:
                # Extract resource_id from result if possible
                resource_id = None
                if result and get_resource_id:
                    try:
                        resource_id = get_resource_id(result)
                    except Exception:
                        pass

                log_audit_event(
                    event_type=event_type,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request=request,
                    success=success,
                    error_message=error_message,
                )

        return wrapper
    return decorator


def get_db_session() -> Session:
    """Get a database session for audit logging."""
    return next(get_db())


class AuditLogger:
    """High-level audit logger for manual use in services."""

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

    def log_login(self, user_id: str, success: bool = True, error: str | None = None) -> None:
        self.log(AuditEventType.USER_LOGIN, user_id=user_id, success=success, error_message=error)

    def log_logout(self, user_id: str) -> None:
        self.log(AuditEventType.USER_LOGOUT, user_id=user_id)

    def log_password_change(self, user_id: str, success: bool = True, error: str | None = None) -> None:
        self.log(AuditEventType.USER_PASSWORD_CHANGE, user_id=user_id, success=success, error_message=error)

    def log_child_create(self, user_id: str, child_id: str, details: dict | None = None) -> None:
        self.log(AuditEventType.CHILD_CREATE, user_id=user_id, resource_type="child", resource_id=child_id, details=details)

    def log_assessment_complete(self, user_id: str, assessment_id: str, child_id: str) -> None:
        self.log(AuditEventType.ASSESSMENT_COMPLETE, user_id=user_id, resource_type="assessment", resource_id=assessment_id,
                 details={"child_id": child_id})

    def log_data_export(self, user_id: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
        self.log(AuditEventType.DATA_EXPORT, user_id=user_id, resource_type=resource_type, resource_id=resource_id, details=details)

    def log_data_deletion(self, user_id: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
        self.log(AuditEventType.DATA_DELETION, user_id=user_id, resource_type=resource_type, resource_id=resource_id, details=details)