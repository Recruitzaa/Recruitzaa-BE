"""SUPER_ADMIN-only user-management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from firebase_admin import exceptions as firebase_exceptions
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.app.models.user import User
from services.auth_service.app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    UpdateUserRolesRequest,
    UpdateUserStatusRequest,
)
from services.auth_service.app.schemas.company import (
    CompanyCreateRequest,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdateRequest,
    EmployerAdminResponse,
    EmployerListResponse,
    EmployerUpdateRequest,
)
from services.auth_service.app.services import (
    admin_user_service,
    company_service,
    firebase_service,
    user_service,
)
from shared.auth.dependencies import get_current_user
from shared.auth.rbac import UserRole
from shared.database.postgres import get_db
from shared.database.redis_client import get_redis_client
from shared.models.company import CompanyStatus
from shared.models.user import AppUser

router = APIRouter(prefix="/admin", tags=["Admin Users"])
logger = logging.getLogger(__name__)


async def require_super_admin(
    current_user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    active_role: Annotated[str | None, Header(alias="X-Active-Role")] = None,
) -> User:
    """Authorize against the current PostgreSQL role and account status."""
    db_user = await user_service.get_user_by_id(session, current_user.id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
        )
    if (
        active_role != UserRole.SUPER_ADMIN.value
        or not db_user.is_active
        or UserRole.SUPER_ADMIN.value not in db_user.available_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires the SUPER_ADMIN role.",
        )
    return db_user


async def _get_target_user(session: AsyncSession, user_id: UUID) -> User:
    user = await user_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


async def _invalidate_auth_cache(user_id: str) -> None:
    """Ensure role and status changes take effect before cached tokens expire."""
    try:
        redis = await get_redis_client()
        user_tokens_key = f"firebase:user:{user_id}:tokens"
        keys = await redis.smembers(user_tokens_key)
        if keys:
            await redis.delete(*keys)
        await redis.delete(user_tokens_key)
    except Exception:
        # Redis is an optional cache; PostgreSQL remains authoritative.
        pass


async def _ensure_admin_invariants(
    session: AsyncSession,
    *,
    actor: User,
    target: User,
    next_roles: list[str],
    next_is_active: bool,
) -> None:
    """Prevent self-lockout and removal of the final active super administrator."""
    target_is_admin = UserRole.SUPER_ADMIN.value in target.available_roles
    target_remains_admin = UserRole.SUPER_ADMIN.value in next_roles and next_is_active
    if actor.id == target.id and not target_remains_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove or deactivate your own SUPER_ADMIN access.",
        )
    if (
        target_is_admin
        and target.is_active
        and not target_remains_admin
        and await admin_user_service.count_active_super_admins(session) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active SUPER_ADMIN account must remain.",
        )


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


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a user in Firebase and Recruitzaa",
)
async def create_user(
    body: AdminUserCreateRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    firebase_uid: str | None = None
    try:
        firebase_uid = await firebase_service.create_firebase_user(
            email=str(body.email),
            password=body.password,
            display_name=body.display_name,
            disabled=not body.is_active,
        )
        user = await admin_user_service.create_user(
            session, firebase_uid=firebase_uid, data=body
        )
        await firebase_service.sync_firebase_access(
            firebase_uid,
            primary_role=user.primary_role,
            available_roles=user.available_roles,
            is_active=user.is_active,
        )
        return admin_user_service.user_to_admin_response(user)
    except firebase_exceptions.AlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Firebase account with this email already exists.",
        ) from exc
    except Exception:
        if firebase_uid:
            try:
                await firebase_service.delete_firebase_user(firebase_uid)
            except Exception:
                logger.exception("Could not compensate Firebase user creation")
        raise


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Get complete user detail",
)
async def get_user_detail(
    user_id: UUID,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    mongo_profile = await admin_user_service.load_mongo_profile(str(user.id))
    return admin_user_service.user_to_admin_response(user, mongo_profile)


@router.put(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Atomically update user access, status, and profile",
)
async def update_user(
    user_id: UUID,
    body: AdminUserUpdateRequest,
    admin: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    await _ensure_admin_invariants(
        session,
        actor=admin,
        target=user,
        next_roles=body.available_roles,
        next_is_active=body.is_active,
    )
    await firebase_service.sync_firebase_access(
        user.firebase_uid,
        primary_role=body.primary_role,
        available_roles=body.available_roles,
        is_active=body.is_active,
    )
    updated = await admin_user_service.update_user(session, user, body)
    await _invalidate_auth_cache(str(user.id))
    return admin_user_service.user_to_admin_response(updated)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user from PostgreSQL, MongoDB, and Firebase",
)
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    user = await _get_target_user(session, user_id)
    if admin.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot delete your own administrator account.",
        )
    await _ensure_admin_invariants(
        session,
        actor=admin,
        target=user,
        next_roles=[],
        next_is_active=False,
    )
    await admin_user_service.delete_mongo_profile(str(user.id))
    await firebase_service.delete_firebase_user(user.firebase_uid)
    await admin_user_service.delete_user(session, user)
    await _invalidate_auth_cache(str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/users/{user_id}/roles",
    response_model=AdminUserResponse,
    summary="Update a user's roles",
)
async def update_user_roles(
    user_id: UUID,
    body: UpdateUserRolesRequest,
    admin: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    await _ensure_admin_invariants(
        session,
        actor=admin,
        target=user,
        next_roles=body.available_roles,
        next_is_active=user.is_active,
    )
    updated = await admin_user_service.update_user_roles(session, user, body)
    await firebase_service.sync_firebase_access(
        user.firebase_uid,
        primary_role=updated.primary_role,
        available_roles=updated.available_roles,
        is_active=updated.is_active,
    )
    await _invalidate_auth_cache(str(user.id))
    return admin_user_service.user_to_admin_response(updated)


@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Activate or deactivate a user",
)
async def update_user_status(
    user_id: UUID,
    body: UpdateUserStatusRequest,
    admin: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    await _ensure_admin_invariants(
        session,
        actor=admin,
        target=user,
        next_roles=user.available_roles,
        next_is_active=body.is_active,
    )
    updated = await admin_user_service.update_user_status(
        session,
        user,
        is_active=body.is_active,
    )
    await firebase_service.sync_firebase_access(
        user.firebase_uid,
        primary_role=updated.primary_role,
        available_roles=updated.available_roles,
        is_active=updated.is_active,
    )
    await _invalidate_auth_cache(str(user.id))
    return admin_user_service.user_to_admin_response(updated)


@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    company_status: Annotated[CompanyStatus | None, Query(alias="status")] = None,
):
    return await company_service.list_companies(
        session,
        page=page,
        page_size=page_size,
        search=search,
        company_status=company_status,
    )


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    body: CompanyCreateRequest,
    admin: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        company = await company_service.create_company(
            session, body, created_by_user_id=str(admin.id)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return company_service.company_to_response(company)


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    company = await company_service.get_company(session, str(company_id))
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found."
        )
    return company_service.company_to_response(company)


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    body: CompanyUpdateRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    company = await company_service.get_company(session, str(company_id))
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found."
        )
    try:
        updated = await company_service.update_company(session, company, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return company_service.company_to_response(updated)


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_company(
    company_id: UUID,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    company = await company_service.get_company(session, str(company_id))
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found."
        )
    try:
        await company_service.delete_company(session, company)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/employers", response_model=EmployerListResponse)
async def list_employers(
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    is_active: bool | None = None,
    company_id: UUID | None = None,
):
    return await company_service.list_employers(
        session,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        company_id=str(company_id) if company_id else None,
    )


@router.put("/employers/{user_id}", response_model=EmployerAdminResponse)
async def update_employer(
    user_id: UUID,
    body: EmployerUpdateRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_target_user(session, user_id)
    if UserRole.EMPLOYER.value not in user.available_roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer account not found.",
        )
    try:
        await company_service.update_employer(session, user, body)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    refreshed = await user_service.get_user_by_id(session, str(user_id))
    await session.refresh(refreshed, ["company_membership"])
    if refreshed.company_membership:
        await session.refresh(refreshed.company_membership, ["company"])
    await firebase_service.sync_firebase_access(
        refreshed.firebase_uid,
        primary_role=refreshed.primary_role,
        available_roles=refreshed.available_roles,
        is_active=refreshed.is_active,
    )
    await _invalidate_auth_cache(str(refreshed.id))
    return company_service.employer_to_response(refreshed)
