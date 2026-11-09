"""
Authentication API Endpoints.

Provides:
- User registration with password strength requirements.
- Secure login and JWT access token issuance.
- Profile inspection and role checks.
- API key generation for programmatic AI agents.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import re
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from core.auth import get_current_user, require_active_user
from core.security import (
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    sanitize_text,
    verify_password,
)
from db.models import User, UserRole
from db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# Mutex to ensure race-safe atomic first-user registration across concurrent requests
_registration_lock = asyncio.Lock()


# ── Schemas ───────────────────────────────────────────────────────────────────

def validate_password_complexity(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit.")
    return v


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    admin_token: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        cleaned = sanitize_text(v.strip())
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValueError("Username may only contain letters, numbers, underscores, and hyphens.")
        return cleaned

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserLoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        return validate_password_complexity(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_reset_password_strength(cls, v: str) -> str:
        return validate_password_complexity(v)


class MessageResponse(BaseModel):
    message: str
    reset_token: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    has_api_key: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


class ApiKeyResponse(BaseModel):
    api_key: str
    message: str = "Store this API key safely. It will not be shown again."


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account with race-safe admin role determination."""
    async with _registration_lock:
        # Check if username or email already exists
        query = select(User).where(or_(User.username == data.username, User.email == data.email))
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with that username or email already exists.",
            )

        # Race-safe admin role determination
        role = UserRole.MEMBER.value

        # 1. If explicit setup token supplied and matches configured admin_setup_token:
        if data.admin_token and settings.admin_setup_token:
            if secrets.compare_digest(data.admin_token, settings.admin_setup_token):
                role = UserRole.ADMIN.value

        # 2. If configured admin_email matches the registered email:
        elif settings.admin_email and data.email.lower() == settings.admin_email.lower():
            role = UserRole.ADMIN.value

        # 3. Otherwise: check if ANY admin user currently exists in database
        else:
            admin_check = await db.execute(select(User.id).where(User.role == UserRole.ADMIN.value))
            has_admin = admin_check.first() is not None
            # Only auto-grant admin to the first user if no setup token requirement is configured
            if not has_admin and not settings.admin_setup_token:
                role = UserRole.ADMIN.value

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            has_api_key=bool(user.api_key_hash),
            created_at=user.created_at,
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username or email and password."""
    target = data.username_or_email.strip()
    query = select(User).where(or_(User.username == target, User.email == target))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username, email, or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    token = create_access_token({
        "sub": user.id,
        "username": user.username,
        "role": user.role,
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            has_api_key=bool(user.api_key_hash),
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(require_active_user),
):
    """Return profile details for current authenticated user."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        has_api_key=bool(current_user.api_key_hash),
        created_at=current_user.created_at,
    )


@router.post("/api-key", response_model=ApiKeyResponse)
async def create_api_key(
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate or rotate an API key for machine-to-machine authentication."""
    raw_key = generate_api_key()
    current_user.api_key_hash = hash_api_key(raw_key)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ApiKeyResponse(
        api_key=raw_key,
        message="Store this API key safely. It will not be shown again.",
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the currently authenticated user."""
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect existing password.",
        )

    current_user.hashed_password = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return MessageResponse(message="Password successfully changed.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request password reset token.
    Uses time-limited signed JWT token (15-minute expiration) with scope='password_reset'.
    """
    query = select(User).where(User.email == data.email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    # Always return success message to prevent user enumeration
    reset_token = None
    if user and user.is_active:
        reset_token = create_access_token(
            data={"sub": user.id, "email": user.email, "scope": "password_reset"},
            expires_delta=timedelta(minutes=15),
        )

    return MessageResponse(
        message="If an account exists with that email, a password reset link has been dispatched.",
        # In non-production or for testing, provide the token in response
        reset_token=reset_token if not settings.is_production else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using a valid, unexpired password reset token.
    """
    payload = decode_access_token(data.reset_token)
    if not payload or payload.get("scope") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated.",
        )

    user.hashed_password = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return MessageResponse(message="Password has been successfully reset. You may now log in.")

