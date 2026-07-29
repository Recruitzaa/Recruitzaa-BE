"""SUPER_ADMIN-only user-management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.app.models.user import User
from services.auth_service.app.schemas.admin import (
    AdminUserListResponse,
    AdminUserResponse,
    UpdateUserRolesRequest,
    UpdateUserStatusRequest,
)
from services.auth_service.app.services import admin_user_service, user_service
from shared.auth.dependencies import get_current_user
from shared.auth.rbac import UserRole
from shared.database.postgres import get_db
from shared.database.redis_client import get_redis_client
from shared.models.user import AppUser

router = APIRouter(prefix="/admin", tags=["Admin Users"])


async def require_super_admin(
    current_user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Authorize against the current PostgreSQL role and account status."""
    db_user = await user_service.get_user_by_id(session, current_user.id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
        )
    if (
        not db_user.is_active
        or UserRole.SUPER_ADMIN.value not in db_user.available_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires the SUPER_ADMIN role.",
        )
    return db_user


async def _get_target_user(session: AsyncSession, user_id: str) -> User:
    user = await user_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


async def _invalidate_auth_cache() -> None:
    """Ensure role and status changes take effect before cached tokens expire."""
    try:
        redis = await get_redis_client()
        keys = await redis.keys("firebase:token:*")
        if keys:
            await redis.delete(*keys)
    except Exception:
        # Redis is an optional cache; PostgreSQL remains authoritative.
        pass


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List and filter users",
)
async def list_users(
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    role: UserRole | None = None,
    is_active: bool | None = None,
):
    return await admin_user_service.list_users(
        session,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        is_active=is_active,
    )


@router.put(
    "/users/{user_id}/roles",
    response_model=AdminUserResponse,
    summary="Update a user's roles",
)
async def update_user_roles(
    user_id: str,
    body: UpdateUserRolesRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    updated = await admin_user_service.update_user_roles(session, user, body)
    await _invalidate_auth_cache()
    return admin_user_service.user_to_admin_response(updated)


@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Activate or deactivate a user",
)
async def update_user_status(
    user_id: str,
    body: UpdateUserStatusRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    updated = await admin_user_service.update_user_status(
        session,
        user,
        is_active=body.is_active,
    )
    await _invalidate_auth_cache()
    return admin_user_service.user_to_admin_response(updated)
