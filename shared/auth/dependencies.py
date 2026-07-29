"""
shared/auth/dependencies.py — FastAPI dependency injection for auth + RBAC.

Usage:
    # Require any authenticated user
    @router.get("/profile")
    async def get_profile(user: AppUser = Depends(get_current_user)):
        ...

    # Require specific role(s)
    @router.post("/jobs")
    async def create_job(user: AppUser = Depends(require_role(UserRole.EMPLOYER))):
        ...

    # Require one of multiple roles
    @router.delete("/jobs/{job_id}")
    async def delete_job(
        user: AppUser = Depends(require_role(UserRole.EMPLOYER, UserRole.SUPER_ADMIN))
    ):
        ...
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from shared.auth.firebase_admin import get_firebase_app
from shared.auth.rbac import UserRole
from shared.models.user import AppUser

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=True)


# Lazy import redis to avoid circular deps at module load time
def _get_redis():
    from shared.database.redis_client import get_redis_client

    return get_redis_client()


def _token_cache_key(token_hash: str) -> str:
    return f"firebase:token:{token_hash}"


async def _get_user_from_cache(token_hash: str) -> AppUser | None:
    """Try to load AppUser from Redis cache."""
    try:
        redis = await _get_redis()
        data = await redis.get(_token_cache_key(token_hash))
        if data:
            return AppUser.model_validate_json(data)
    except Exception as exc:
        logger.warning("Redis cache miss (error): %s", exc)
    return None


async def _cache_user(token_hash: str, user: AppUser, ttl: int = 300) -> None:
    """Cache AppUser in Redis for TTL seconds (default 5 min)."""
    try:
        redis = await _get_redis()
        await redis.setex(
            _token_cache_key(token_hash),
            ttl,
            user.model_dump_json(),
        )
    except Exception as exc:
        logger.warning("Redis cache write failed: %s", exc)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AppUser:
    """
    FastAPI dependency: verify Firebase ID token and return AppUser.

    Steps:
    1. Hash the token (SHA-256) to use as cache key
    2. Check Redis cache (TTL 5min)
    3. On miss: verify token with Firebase Admin SDK
    4. Load full AppUser from PostgreSQL (via user_service)
    5. Cache and return
    """
    token = credentials.credentials
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # 1. Cache hit
    cached = await _get_user_from_cache(token_hash)
    if cached:
        return cached

    # 2. Firebase verification
    get_firebase_app()  # ensure initialized
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except firebase_auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please sign in again.",
        )
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    firebase_uid: str = decoded["uid"]

    # 3. Load AppUser from PostgreSQL
    from services.auth_service.app.services.user_service import get_user_by_firebase_uid
    from shared.database.postgres import get_db_session

    try:
        async with get_db_session() as session:
            user = await get_user_by_firebase_uid(session, firebase_uid)
    except Exception as exc:
        logger.error("DB lookup failed for uid=%s: %s", firebase_uid, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load user profile.",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    # 4. Cache result
    await _cache_user(token_hash, user)
    return user


def require_role(*roles: UserRole):
    """
    FastAPI dependency factory: require the user's active role to be in `roles`.

    Checks `active_role` first (set when user picks role in Launchpad),
    then falls back to `primary_role`.
    """
    allowed = set(roles)

    async def _check_role(user: AppUser = Depends(get_current_user)) -> AppUser:
        effective_role = user.active_role or user.primary_role
        if effective_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {[r.value for r in allowed]}. "
                f"Your active role is: {effective_role.value}",
            )
        return user

    return _check_role
