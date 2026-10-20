"""Authentication schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.utils import BCRYPT_MAX_BYTES


def _check_password(cls, value: str) -> str:  # noqa: ARG001 - pydantic passes the model class
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    if value.strip() != value or not value.strip():
        raise ValueError("Password must not start or end with whitespace")
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="parent", pattern="^(parent|educator)$")

    _password = field_validator("password")(_check_password)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name is required")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    """The refresh token is only ever delivered as an HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class CurrentUser(BaseModel):
    id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str
    is_active: bool


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)

    _password = field_validator("new_password")(_check_password)
