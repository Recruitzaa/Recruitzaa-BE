"""Authenticated employer company-registration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.app.models.user import User
from services.auth_service.app.schemas.company import (
    CompanyResponse,
    EmployerCompanyRegistrationRequest,
)
from services.auth_service.app.services import company_service, user_service
from shared.auth.dependencies import get_current_user
from shared.auth.rbac import UserRole
from shared.database.postgres import get_db
from shared.models.user import AppUser

router = APIRouter(prefix="/companies", tags=["Companies"])


async def require_employer(
    current_user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await user_service.get_user_by_id(session, current_user.id)
    if (
        user is None
        or not user.is_active
        or UserRole.EMPLOYER.value not in user.available_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active EMPLOYER role is required.",
        )
    return user


@router.post(
    "/register",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_employer_company(
    body: EmployerCompanyRegistrationRequest,
    employer: Annotated[User, Depends(require_employer)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await company_service.register_company_for_employer(
        session,
        employer,
        company_name=body.company_name,
        company_website=body.company_website,
    )
