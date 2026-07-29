"""Admin user-management service layer."""

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.auth_service.app.models.user import User, UserProfile
from services.auth_service.app.schemas.admin import (
    AdminUserListResponse,
    AdminUserResponse,
    UpdateUserRolesRequest,
)
from shared.auth.rbac import UserRole


async def list_users(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> AdminUserListResponse:
    """Return a filtered, newest-first page of users and PostgreSQL profiles."""
    filters = []
    normalized_search = search.strip() if search else None
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                User.email.ilike(pattern),
                UserProfile.display_name.ilike(pattern),
            )
        )
    if role is not None:
        filters.append(User.available_roles.any(role.value))
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    count_query = (
        select(func.count(User.id))
        .select_from(User)
        .outerjoin(UserProfile)
        .where(*filters)
    )
    total = int((await session.scalar(count_query)) or 0)

    users_query = (
        select(User)
        .options(selectinload(User.profile))
        .outerjoin(UserProfile)
        .where(*filters)
        .order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = list((await session.scalars(users_query)).all())
    total_pages = ceil(total / page_size) if total else 0

    return AdminUserListResponse(
        items=[user_to_admin_response(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


async def update_user_roles(
    session: AsyncSession,
    user: User,
    data: UpdateUserRolesRequest,
) -> User:
    """Replace a user's primary and available roles."""
    user.primary_role = data.primary_role.value
    user.available_roles = [role.value for role in data.available_roles]
    await session.flush()
    return user


async def update_user_status(
    session: AsyncSession,
    user: User,
    *,
    is_active: bool,
) -> User:
    """Activate or deactivate a user account."""
    user.is_active = is_active
    await session.flush()
    return user


def user_to_admin_response(user: User) -> AdminUserResponse:
    """Convert an eagerly loaded user and profile to the admin API shape."""
    profile = user.profile
    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        firebase_uid=user.firebase_uid,
        primary_role=UserRole(user.primary_role),
        available_roles=[UserRole(role) for role in user.available_roles],
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        display_name=profile.display_name if profile else None,
        photo_url=profile.photo_url if profile else None,
        phone=profile.phone if profile else None,
        location=profile.location if profile else None,
        bio=profile.bio if profile else None,
        summary=profile.summary if profile else None,
        notice_period=profile.notice_period if profile else None,
        is_currently_employed=(profile.is_employed or False) if profile else False,
        current_company=profile.current_company if profile else None,
        current_role=profile.current_role if profile else None,
        current_salary=profile.current_salary if profile else None,
    )
