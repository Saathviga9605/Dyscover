"""Authentication module."""

from .schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    CurrentUser,
    PasswordChange,
    AuthErrorResponse,
)
from .utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    TokenPair,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "RefreshTokenRequest",
    "UserResponse",
    "CurrentUser",
    "PasswordChange",
    "AuthErrorResponse",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_secure_token",
    "TokenPair",
]