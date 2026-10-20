"""Privacy endpoints: data export, data summary and account deletion.

These implement the platform's documented export/erasure behaviour. They are
not, by themselves, evidence of compliance with GDPR, COPPA or any other law.
"""


import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import AuditEventType, AuditLogger
from app.auth.deps import get_current_user
from app.auth.routes import REFRESH_COOKIE, REFRESH_COOKIE_PATH
from app.auth.utils import verify_password
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import AssessmentSession, ChildProfile, Conversation, GameSession, InteractionEvent, PracticeSession, SpeechSession, Trial, User
from app.privacy.service import collect_user_data, delete_account

router = APIRouter(prefix="/api/privacy", tags=["privacy"])
logger = logging.getLogger("dyscover.privacy")


class AccountDeletionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.get("/export")
@limiter.limit("5/minute")
def export_user_data(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    data = collect_user_data(db, current_user)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("user_data.json", json.dumps(data, indent=2, ensure_ascii=False, default=str))
        archive.writestr(
            "export_summary.json",
            json.dumps(
                {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "export_schema_version": data["export_schema_version"],
                    "children_count": len(data["children"]),
                    "assessments_count": sum(len(child["assessments"]) for child in data["children"]),
                    "practice_sessions_count": sum(len(child["practice_sessions"]) for child in data["children"]),
                    "lexi_conversations_count": len(data["lexi_conversations"]),
                },
                indent=2,
            ),
        )
    AuditLogger(request).log(AuditEventType.DATA_EXPORT, user_id=str(current_user.id), resource_type="user_data", resource_id=str(current_user.id))
    filename = f"dyscover_export_{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip"
    return Response(content=buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def delete_own_account(payload: AccountDeletionRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Permanently delete the account and everything derived from it. Requires the password."""
    audit = AuditLogger(request)
    if not verify_password(payload.password, current_user.password_hash):
        audit.log(AuditEventType.DATA_DELETION, user_id=str(current_user.id), success=False, error_message="wrong_password")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect")
    user_id = str(current_user.id)
    try:
        counts = delete_account(db, current_user)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Account deletion failed")
        audit.log(AuditEventType.DATA_DELETION, user_id=user_id, success=False, error_message="deletion_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account deletion failed; no data was removed")
    audit.log(AuditEventType.DATA_DELETION, user_id=user_id, resource_type="user_account", resource_id=user_id, details=counts)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response


@router.get("/data-summary")
def get_data_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    children = list(db.scalars(select(ChildProfile).where(ChildProfile.owner_id == current_user.id)))
    child_ids = [child.id for child in children]
    assessments = select(AssessmentSession.id).where(AssessmentSession.child_id.in_(child_ids))
    trials = select(Trial.id).where(Trial.game_session_id.in_(select(GameSession.id).where(GameSession.assessment_session_id.in_(assessments))))

    def count(statement) -> int:
        return int(db.scalar(statement) or 0) if child_ids else 0

    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "children": {
            "count": len(children),
            "details": [{"id": str(child.id), "display_name": child.display_name, "birth_year": child.birth_year} for child in children],
        },
        "assessments": {"count": count(select(func.count()).select_from(AssessmentSession).where(AssessmentSession.child_id.in_(child_ids)))},
        "trials": {"count": count(select(func.count()).select_from(Trial).where(Trial.id.in_(trials)))},
        "interaction_events": {"count": count(select(func.count()).select_from(InteractionEvent).where(InteractionEvent.trial_id.in_(trials)))},
        "speech_sessions": {"count": count(select(func.count()).select_from(SpeechSession).where(SpeechSession.assessment_id.in_(assessments)))},
        "practice_sessions": {"count": count(select(func.count()).select_from(PracticeSession).where(PracticeSession.child_id.in_(child_ids)))},
        "lexi_conversations": {"count": int(db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == current_user.id)) or 0)},
        "retention": "Data is kept until you delete it or delete your account. Raw audio is never stored.",
    }
