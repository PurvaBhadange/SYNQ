"""
SYNQ Authentication & Authorization Dependency Module.

Provides:
- OAuth2 Bearer token and X-API-Key header authentication.
- Role-Based Access Control (RBAC): Admin, Member, Viewer.
- User verification against database.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from core.security import decode_access_token, hash_api_key
from db.models import User, UserRole
from db.session import get_db

settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Authenticate request via JWT Bearer token or X-API-Key header.
    If auth_enabled is False and no credentials provided, returns None (allowing dev mode).
    """
    # 1. Check Bearer JWT token
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and "sub" in payload:
            user_id = payload["sub"]
            query = select(User).where(User.id == user_id)
            result = await db.execute(query)
            user = result.scalar_one_or_none()
            if user:
                return user

    # 2. Check X-API-Key header
    if api_key:
        key_hash = hash_api_key(api_key)
        query = select(User).where(User.api_key_hash == key_hash)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        if user:
            return user

    # If auth is required, raise 401 Unauthorized
    if settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return None


async def require_active_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """Enforces that an active authenticated user is present."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return current_user


async def require_admin(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Enforces that the authenticated user has the 'admin' role.
    If auth_enabled is False, allows access in local development.
    """
    if not settings.auth_enabled:
        # Dev mode fallback admin
        if current_user is None:
            return User(
                id="dev-admin",
                username="admin",
                email="admin@synq.local",
                role=UserRole.ADMIN.value,
                is_active=True,
                hashed_password="",
            )
        return current_user

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to access this resource.",
        )

    return current_user
