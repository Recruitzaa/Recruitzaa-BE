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
    user_service,
)
from shared.auth.dependencies import get_current_user
from shared.auth.rbac import UserRole
from shared.database.postgres import get_db
from shared.database.redis_client import get_redis_client
from shared.models.company import CompanyStatus
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


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    body: CompanyUpdateRequest,
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    company = await company_service.get_company(session, company_id)
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


@router.get("/employers", response_model=EmployerListResponse)
async def list_employers(
    _: Annotated[User, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    is_active: bool | None = None,
    company_id: str | None = None,
):
    return await company_service.list_employers(
        session,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        company_id=company_id,
    )


@router.put("/employers/{user_id}", response_model=EmployerAdminResponse)
async def update_employer(
    user_id: str,
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
    refreshed = await user_service.get_user_by_id(session, user_id)
    await session.refresh(refreshed, ["company_membership"])
    if refreshed.company_membership:
        await session.refresh(refreshed.company_membership, ["company"])
    await _invalidate_auth_cache()
    return company_service.employer_to_response(refreshed)
