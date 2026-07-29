"""
Auth Service — /auth router.

All endpoints defined in BE_PLAN_3 Section 5 Auth Service table.
"""
import logging
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import auth as firebase_auth
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.app.schemas.auth import (
    AppUserResponse,
    AuthResponse,
    FCMTokenRequest,
    LogoutResponse,
    RegisterRequest,
    UpdateProfileRequest,
    VerifyTokenRequest,
)
from services.auth_service.app.services import firebase_service, user_service
from shared.auth.dependencies import get_current_user
from shared.database.postgres import get_db
from shared.database.redis_client import get_redis_client
from shared.messaging import topics
from shared.messaging.kafka_producer import RecruitzaaProducer
from shared.models.user import AppUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# ─── Kafka producer (lazy) ───────────────────────────────────────────────────
_producer = RecruitzaaProducer()


# ─── POST /auth/register ─────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register with Firebase token",
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    1. Verify Firebase ID token
    2. Create user in PostgreSQL (idempotent)
    3. Create empty candidate_profile in MongoDB
    4. Emit user.registered Kafka event
    5. Return AppUser with availableRoles[]
    """
    # 1. Verify token
    try:
        token_data = firebase_service.verify_firebase_token(body.firebase_token)
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token.",
        )
    except Exception as exc:
        logger.error("Firebase verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed.",
        )

    # 2. Create/fetch user in PostgreSQL
    user = await user_service.create_user(
        session=session,
        firebase_uid=token_data["uid"],
        email=token_data["email"],
        requested_role=body.requested_role,
        display_name=body.display_name or token_data.get("name"),
        photo_url=token_data.get("picture"),
    )

    # 3. Create empty MongoDB profile (fire-and-forget)
    try:
        from datetime import datetime

        from shared.database.mongo import get_mongo_db
        db = get_mongo_db()
        await db.candidate_profiles.update_one(
            {"user_id": str(user.id)},
            {
                "$setOnInsert": {
                    "user_id": str(user.id),
                    "skills_flat": [],
                    "experience": [],
                    "education": [],
                    "certifications": [],
                    "resume_versions": [],
                    "profile_completion_pct": 0,
                    "created_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("MongoDB profile init failed (non-fatal): %s", exc)

    # 4. Emit Kafka event (non-blocking)
    try:
        await _producer.send_event(
            topics.USER_REGISTERED,
            {
                "user_id": str(user.id),
                "email": user.email,
                "role": user.primary_role,
                "available_roles": user.available_roles,
            },
            key=str(user.id),
        )
    except Exception as exc:
        logger.warning("Kafka emit failed (non-fatal): %s", exc)

    return AuthResponse(
        user=user_service.user_to_response(user),
        message="Registration successful",
    )


# ─── POST /auth/verify ───────────────────────────────────────────────────────
@router.post(
    "/verify",
    response_model=AuthResponse,
    summary="Verify token and return AppUser",
)
async def verify_token(
    body: VerifyTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Verify Firebase token and return AppUser with availableRoles[].
    Used by FE on app load to restore session.
    """
    try:
        token_data = firebase_service.verify_firebase_token(body.firebase_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user = await user_service.get_user_by_firebase_uid(session, token_data["uid"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered. Please call /auth/register first.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated.",
        )

    return AuthResponse(user=user_service.user_to_response(user))


# ─── GET /auth/me ────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=AppUserResponse,
    summary="Get current user (CRITICAL: must return availableRoles[])",
)
async def get_me(
    current_user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns full AppUser in camelCase.

    This is THE most critical endpoint — FE Launchpad reads availableRoles[]
    from this response to show role-selection cards.
    RoleGuard depends on this being correct for ALL protected routes.
    """
    # Refresh from DB to get latest available_roles (may have been updated by admin)
    db_user = await user_service.get_user_by_id(session, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user_service.user_to_response(db_user)


# ─── PUT /auth/me ────────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=AppUserResponse,
    summary="Update current user's profile",
)
async def update_me(
    body: UpdateProfileRequest,
    current_user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    db_user = await user_service.get_user_by_id(session, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated = await user_service.update_profile(session, db_user, body)

    # Invalidate Redis cache
    try:
        redis = await get_redis_client()
        await redis.delete(f"profile:{current_user.id}")
    except Exception:
        pass

    return user_service.user_to_response(updated)


# ─── POST /auth/logout ───────────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout and invalidate Redis token cache",
)
async def logout(
    current_user: AppUser = Depends(get_current_user),
):
    """
    Clears the Redis token cache for this user.
    Token revocation on Firebase is optional (called for security-sensitive logout).
    """
    try:
        redis = await get_redis_client()
        # Clear all cached tokens for this user (pattern delete)
        pattern = "firebase:token:*"
        keys = await redis.keys(pattern)
        # We don't store user->token mapping, so we clear all token caches
        # (they'll re-verify on next request). In production, store token->user mapping.
        if keys:
            await redis.delete(*keys)
    except Exception as exc:
        logger.warning("Redis logout cache clear failed: %s", exc)

    return LogoutResponse()


# ─── POST /auth/fcm-token ────────────────────────────────────────────────────
@router.post(
    "/fcm-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Register FCM push token",
)
async def register_fcm_token(
    body: FCMTokenRequest,
    current_user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    db_user = await user_service.get_user_by_id(session, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await user_service.add_fcm_token(session, db_user, body)
