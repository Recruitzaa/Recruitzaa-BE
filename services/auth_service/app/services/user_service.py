"""
Auth Service — User service layer.

Handles all PostgreSQL CRUD for users + user_profiles.
"""

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.auth_service.app.models.user import User, UserFCMToken, UserProfile
from services.auth_service.app.schemas.auth import (
    AppUserResponse,
    FCMTokenRequest,
    UpdateProfileRequest,
)
from shared.auth.rbac import UserRole

logger = logging.getLogger(__name__)


def user_to_app_user(user: User):
    """Convert an ORM user to the shared authentication model."""
    from shared.models.user import AppUser

    profile = user.profile
    return AppUser(
        id=str(user.id),
        firebase_uid=user.firebase_uid,
        email=user.email,
        primary_role=UserRole(user.primary_role),
        available_roles=[UserRole(role) for role in user.available_roles],
        display_name=profile.display_name if profile else None,
        photo_url=profile.photo_url if profile else None,
        phone=profile.phone if profile else None,
        location=profile.location if profile else None,
        bio=profile.bio if profile else None,
        summary=profile.summary if profile else None,
        is_currently_employed=(profile.is_employed or False) if profile else False,
        current_company=profile.current_company if profile else None,
        current_role=profile.current_role if profile else None,
        current_salary=profile.current_salary if profile else None,
        notice_period=profile.notice_period if profile else None,
        is_active=user.is_active,
    )


async def get_user_by_firebase_uid(
    session: AsyncSession, firebase_uid: str
) -> User | None:
    """Fetch user + profile by Firebase UID (eager load profile)."""
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.firebase_uid == firebase_uid)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    firebase_uid: str,
    email: str,
    requested_role: UserRole,
    display_name: str | None = None,
    photo_url: str | None = None,
) -> User:
    """
    Create a new user + empty profile.

    This is idempotent — if firebase_uid already exists, return existing user.
    Admin emails (from ADMIN_EMAILS env var) automatically get all 5 roles.
    """
    # Idempotency check
    existing = await get_user_by_firebase_uid(session, firebase_uid)
    if existing:
        logger.info(
            "User already exists for firebase_uid=%s — returning existing", firebase_uid
        )
        return existing

    # Check if this email is an admin — auto-grant all 5 roles
    admin_emails_raw = os.environ.get("ADMIN_EMAILS", "")
    admin_emails = [e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()]
    all_roles = [r.value for r in UserRole]

    requested_role_str = (
        requested_role.value
        if hasattr(requested_role, "value")
        else str(requested_role)
    )

    if email.lower() in admin_emails:
        roles = all_roles
        role = requested_role_str
        logger.info("Admin email detected (%s) — granting all roles", email)
    else:
        roles = [requested_role_str]
        role = requested_role_str

    user = User(
        firebase_uid=firebase_uid,
        email=email,
        primary_role=role,
        available_roles=roles,
        is_active=True,
    )
    session.add(user)
    await session.flush()  # get user.id before creating profile

    profile = UserProfile(
        user_id=user.id,
        display_name=display_name,
        photo_url=photo_url,
    )
    session.add(profile)
    await session.flush()

    # Eager load the profile we just created
    await session.refresh(user, ["profile"])
    logger.info("Created user id=%s email=%s role=%s", user.id, email, requested_role)
    return user


async def update_profile(
    session: AsyncSession,
    user: User,
    data: UpdateProfileRequest,
) -> User:
    """Update user_profiles fields from UpdateProfileRequest."""
    profile = user.profile
    if profile is None:
        profile = UserProfile(user_id=user.id)
        session.add(profile)

    update_map = {
        "display_name": data.display_name,
        "phone": data.phone,
        "photo_url": data.photo_url,
        "location": data.location,
        "bio": data.bio,
        "summary": data.summary,
        "notice_period": data.notice_period,
        "is_employed": data.is_currently_employed,
        "current_company": data.current_company,
        "current_role": data.current_role,
        "current_salary": data.current_salary,
    }
    for field, value in update_map.items():
        if value is not None:
            setattr(profile, field, value)

    # Update user.updated_at
    user.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(user, ["profile"])
    return user


async def add_fcm_token(
    session: AsyncSession,
    user: User,
    data: FCMTokenRequest,
) -> None:
    """Register an FCM push token for the user (upsert by token value)."""
    # Check if token already exists
    result = await session.execute(
        select(UserFCMToken).where(UserFCMToken.token == data.token)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return  # already registered

    token = UserFCMToken(
        user_id=user.id,
        token=data.token,
        platform=data.platform,
    )
    session.add(token)
    await session.flush()
    logger.info(
        "FCM token registered for user_id=%s platform=%s", user.id, data.platform
    )


async def deactivate_user(session: AsyncSession, user_id: str) -> None:
    """Deactivate a user account (SUPER_ADMIN only)."""
    await session.execute(
        update(User).where(User.id == user_id).values(is_active=False)
    )


def user_to_response(user: User) -> AppUserResponse:
    """
    Convert SQLAlchemy User ORM object → AppUserResponse Pydantic schema.

    This is the single place that maps DB fields to the FE AppUser interface.
    camelCase serialization is handled by CamelModel alias_generator.
    """
    app_user = user_to_app_user(user)
    return AppUserResponse(
        id=app_user.id,
        email=app_user.email,
        firebase_uid=app_user.firebase_uid,
        role=app_user.primary_role,  # backward-compat field
        available_roles=app_user.available_roles,
        display_name=app_user.display_name,
        photo_url=app_user.photo_url,
        phone=app_user.phone,
        location=app_user.location,
        bio=app_user.bio,
        summary=app_user.summary,
        is_currently_employed=app_user.is_currently_employed,
        current_company=app_user.current_company,
        current_role=app_user.current_role,
        current_salary=app_user.current_salary,
        notice_period=app_user.notice_period,
        skills=[],  # populated from MongoDB candidate_profiles
        resume_file_name=None,  # populated from MongoDB
        resume_file_size=None,  # populated from MongoDB
        is_active=app_user.is_active,
    )
