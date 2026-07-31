"""Admin user-management service layer."""

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.auth_service.app.models.user import User, UserProfile
from services.auth_service.app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
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
    user.primary_role = data.primary_role
    user.available_roles = data.available_roles
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


async def create_user(
    session: AsyncSession,
    *,
    firebase_uid: str,
    data: AdminUserCreateRequest,
) -> User:
    """Create the PostgreSQL half of an administrator-provisioned account."""
    user = User(
        firebase_uid=firebase_uid,
        email=str(data.email).lower(),
        primary_role=data.primary_role,
        available_roles=data.available_roles,
        is_active=data.is_active,
    )
    user.profile = UserProfile(display_name=data.display_name)
    session.add(user)
    await session.flush()
    await session.refresh(user, ["profile"])
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    data: AdminUserUpdateRequest,
) -> User:
    """Apply the admin editor as one database transaction."""
    user.primary_role = data.primary_role
    user.available_roles = data.available_roles
    user.is_active = data.is_active
    if user.profile is None:
        user.profile = UserProfile()
    user.profile.display_name = data.display_name
    user.profile.phone = data.phone
    user.profile.location = data.location
    user.profile.bio = data.bio
    await session.flush()
    return user


async def count_active_super_admins(session: AsyncSession) -> int:
    """Count accounts that can recover administrative access."""
    count_query = select(func.count(User.id)).where(
        User.is_active.is_(True),
        User.available_roles.any(UserRole.SUPER_ADMIN.value),
    )
    return int((await session.scalar(count_query)) or 0)


async def delete_user(session: AsyncSession, user: User) -> None:
    """Delete PostgreSQL user data; ORM/database cascades remove dependants."""
    await session.delete(user)
    await session.flush()


async def load_mongo_profile(user_id: str) -> dict:
    """Return the optional candidate profile projection used by admin detail."""
    from shared.database.mongo import get_mongo_db

    profile = await get_mongo_db().candidate_profiles.find_one(
        {"user_id": user_id},
        {
            "_id": 0,
            "skills_flat": 1,
            "resume_versions": {"$slice": -1},
        },
    )
    return profile or {}


async def delete_mongo_profile(user_id: str) -> None:
    """Remove role-specific document data for a deleted account."""
    from shared.database.mongo import get_mongo_db

    db = get_mongo_db()
    await db.candidate_profiles.delete_many({"user_id": user_id})
    await db.employer_profiles.delete_many({"user_id": user_id})


def user_to_admin_response(
    user: User, mongo_profile: dict | None = None
) -> AdminUserResponse:
    """Convert an eagerly loaded user and profile to the admin API shape."""
    profile = user.profile
    mongo_profile = mongo_profile or {}
    resume_versions = mongo_profile.get("resume_versions") or []
    latest_resume = resume_versions[-1] if resume_versions else {}
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
        skills=mongo_profile.get("skills_flat") or [],
        resume_file_name=latest_resume.get("file_name"),
        resume_file_size=latest_resume.get("file_size"),
    )
