"""Authentication routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    CurrentUser,
    PasswordChange,
    AuthErrorResponse,
)
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
)
from app.audit import AuditEventType, AuditLogger
from app.core.config import get_settings
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["authentication"])

security = HTTPBearer(auto_error=False)

settings = get_settings()

# In-memory refresh token store (use Redis in production)
_refresh_token_store: dict[str, dict] = {}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user from the access token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token")

    user = db.get(User, user_uuid)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)) -> User:
    """Register a new user account."""
    # Check if email already exists
    if payload.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Hash password and create user
    hashed_password = hash_password(payload.password)
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
    )
    user.password_hash = hashed_password  # type: ignore

    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    audit = AuditLogger(request)
    audit.log(AuditEventType.USER_REGISTER, user_id=str(user.id), success=True)

    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate user and return access + refresh tokens."""
    audit = AuditLogger(request)

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        audit.log(AuditEventType.USER_LOGIN, user_id=payload.email, success=False, error_message="User not found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Verify password
    stored_hash = getattr(user, "password_hash", None)
    if not stored_hash or not verify_password(payload.password, stored_hash):
        audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id), success=False, error_message="Invalid password")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id), success=False, error_message="Account inactive")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    # Create tokens
    access_token = create_access_token(str(user.id), extra_claims={"role": user.role, "email": user.email or ""})
    refresh_token = create_refresh_token(str(user.id))

    # Store refresh token (in production, use Redis with TTL)
    _refresh_token_store[refresh_token] = {
        "user_id": str(user.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    # Audit log successful login
    audit.log(AuditEventType.USER_LOGIN, user_id=str(user.id), success=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes in seconds
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, payload: Optional[RefreshTokenRequest] = None, db: Session = Depends(get_db)) -> TokenResponse:
    """Refresh access token using refresh token."""
    # Try to get refresh token from body or cookie
    refresh_token = payload.refresh_token if payload else request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")

    # Validate refresh token
    token_data = _refresh_token_store.get(refresh_token)
    if not token_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # Verify token is valid JWT
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        # Remove invalid token from store
        _refresh_token_store.pop(refresh_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        _refresh_token_store.pop(refresh_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        _refresh_token_store.pop(refresh_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token")

    user = db.get(User, user_uuid)
    if not user or not user.is_active:
        _refresh_token_store.pop(refresh_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Create new token pair
    new_access_token = create_access_token(str(user.id), extra_claims={"role": user.role, "email": user.email or ""})
    new_refresh_token = create_refresh_token(str(user.id))

    # Rotate refresh token
    _refresh_token_store.pop(refresh_token, None)
    _refresh_token_store[new_refresh_token] = {
        "user_id": str(user.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=30 * 60,
    )


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    """Logout user by invalidating refresh token."""
    audit = AuditLogger(request)
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        _refresh_token_store.pop(refresh_token, None)

    response.delete_cookie(key="refresh_token", httponly=True, secure=settings.app_env == "production", samesite="lax")
    audit.log(AuditEventType.USER_LOGOUT, success=True)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=CurrentUser)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> CurrentUser:
    """Get current user info."""
    return CurrentUser(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )


@router.post("/change-password", response_model=dict[str, str])
def change_password(payload: PasswordChange, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    """Change user password."""
    audit = AuditLogger(request)
    stored_hash = getattr(current_user, "password_hash", None)
    if not stored_hash or not verify_password(payload.current_password, stored_hash):
        audit.log(AuditEventType.USER_PASSWORD_CHANGE, user_id=str(current_user.id), success=False, error_message="Current password incorrect")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    # Hash and store new password
    current_user.password_hash = hash_password(payload.new_password)  # type: ignore
    db.commit()
    audit.log(AuditEventType.USER_PASSWORD_CHANGE, user_id=str(current_user.id), success=True)
    return {"message": "Password changed successfully"}