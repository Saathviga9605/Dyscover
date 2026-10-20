"""FastAPI dependencies for the authenticated caller."""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.utils import decode_access_token
from app.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)

CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "dyscover"


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("Invalid or expired token")
    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError):
        raise _unauthorized("Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise _unauthorized("Invalid or expired token")
    request.state.user_id = str(user.id)
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    allowed = set(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account type cannot perform this action")
        return user

    return dependency


def require_csrf_header(request: Request) -> None:
    """Cookie-authenticated endpoints require a custom header.

    Browsers cannot attach custom headers to cross-site requests without a CORS
    preflight, which only allow-listed origins pass.
    """
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing request verification header")
