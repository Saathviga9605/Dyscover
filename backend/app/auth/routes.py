"""Authentication routes.

Session model:
- Access token: short-lived JWT sent as ``Authorization: Bearer``. It carries the
  user's ``token_version`` so a password change invalidates outstanding tokens.
- Refresh token: opaque random value in an HttpOnly cookie scoped to /api/auth,
  stored server-side only as a SHA-256 digest, rotated on every use. Re-use of a
  rotated token revokes the entire token family.
"""


from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import AuditEventType, AuditLogger
from app.auth.deps import get_current_user, require_csrf_header
from app.auth.schemas import CurrentUser, PasswordChange, TokenResponse, UserLogin, UserRegister, UserResponse
from app.auth.utils import create_access_token, hash_password, hash_refresh_token, new_refresh_token, verify_password
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.time import utcnow
from app.database import get_db
from app.models import RefreshToken, User

router = APIRouter(prefix="/api/auth", tags=["authentication"])

REFRESH_COOKIE = "dyscover_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
_settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite=_settings.refresh_cookie_samesite.lower(),
        max_age=_settings.refresh_token_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite=_settings.refresh_cookie_samesite.lower(),
    )


def _issue_session(db: Session, response: Response, user: User, family_id=None) -> TokenResponse:
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id or uuid4(),
            expires_at=utcnow() + timedelta(days=_settings.refresh_token_days),
        )
    )
    db.commit()
    _set_refresh_cookie(response, raw)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.token_version),
        expires_in=_settings.access_token_minutes * 60,
    )


def _revoke_all_refresh_tokens(db: Session, user: User) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.rate_limit_auth)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)) -> User:
    audit = AuditLogger(request)
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        audit.log(AuditEventType.USER_REGISTER, success=False, error_message="duplicate_email")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    db.refresh(user)
    audit.log(AuditEventType.USER_REGISTER, user_id=str(user.id), success=True)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_settings.rate_limit_auth)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    audit = AuditLogger(request)
    user = db.scalar(select(User).where(User.email == payload.email))
    # verify_password runs a dummy bcrypt check for unknown users (timing parity).
    if not verify_password(payload.password, user.password_hash if user else None) or user is None:
        audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id) if user else None, success=False, error_message="invalid_credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id), success=False, error_message="inactive")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    tokens = _issue_session(db, response, user)
    audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id), success=True)
    return tokens


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_csrf_header)])
@limiter.limit("60/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    now = utcnow()
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if record.revoked_at is not None:
        # A rotated token was presented again: treat the family as compromised.
        db.execute(update(RefreshToken).where(RefreshToken.family_id == record.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
        db.commit()
        AuditLogger(request).log(AuditEventType.USER_LOGIN, user_id=str(record.user_id), success=False, error_message="refresh_token_reuse")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    user = db.get(User, record.user_id)
    if record.expires_at <= now or user is None or not user.is_active:
        record.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    record.revoked_at = now
    return _issue_session(db, response, user, family_id=record.family_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_header)])
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    raw = request.cookies.get(REFRESH_COOKIE)
    user_id = None
    if raw:
        record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        if record is not None:
            user_id = str(record.user_id)
            db.execute(update(RefreshToken).where(RefreshToken.family_id == record.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))
            db.commit()
    _clear_refresh_cookie(response)
    AuditLogger(request).log(AuditEventType.USER_LOGOUT, user_id=user_id, success=True)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_everywhere(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    current_user.token_version += 1
    _revoke_all_refresh_tokens(db, current_user)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    AuditLogger(request).log(AuditEventType.USER_LOGOUT, user_id=str(current_user.id), details={"scope": "all_sessions"})
    return response


@router.get("/me", response_model=CurrentUser)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )


@router.post("/change-password", response_model=TokenResponse)
@limiter.limit(_settings.rate_limit_auth)
def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Change password, revoke every other session, and return a fresh session for this device."""
    audit = AuditLogger(request)
    if not verify_password(payload.current_password, current_user.password_hash):
        audit.log(AuditEventType.USER_PASSWORD_CHANGE, user_id=str(current_user.id), success=False, error_message="wrong_current_password")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from the current password")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1
    _revoke_all_refresh_tokens(db, current_user)
    tokens = _issue_session(db, response, current_user)
    audit.log(AuditEventType.USER_PASSWORD_CHANGE, user_id=str(current_user.id), success=True)
    return tokens


__all__ = ["router", "get_current_user", "REFRESH_COOKIE"]
