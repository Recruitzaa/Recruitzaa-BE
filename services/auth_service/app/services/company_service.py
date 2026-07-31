"""Company registration and administration services."""

from math import ceil
from urllib.parse import urlparse

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.auth_service.app.models.user import (
    Company,
    CompanyMember,
    User,
    UserProfile,
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
from shared.auth.rbac import UserRole
from shared.models.company import CompanyMemberRole, CompanyPlan, CompanyStatus


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def normalize_domain(website: str | None) -> str | None:
    if not website:
        return None
    value = website.strip().lower()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Company website must use http or https.")
    domain = parsed.hostname
    if not domain:
        raise ValueError("Company website must contain a valid domain.")
    normalized = domain.removeprefix("www.").rstrip(".")
    if "." not in normalized or any(not part for part in normalized.split(".")):
        raise ValueError("Company website must contain a valid public domain.")
    return normalized


async def get_company(session: AsyncSession, company_id: str) -> Company | None:
    return await session.scalar(
        select(Company)
        .options(selectinload(Company.members))
        .where(Company.id == company_id)
    )


async def create_company(
    session: AsyncSession,
    data: CompanyCreateRequest,
    *,
    created_by_user_id: str | None = None,
) -> Company:
    domain = normalize_domain(data.website)
    if domain:
        existing = await session.scalar(select(Company).where(Company.domain == domain))
        if existing:
            raise ValueError("A company with this website domain already exists.")

    company = Company(
        name=data.name.strip(),
        domain=domain,
        website=data.website,
        industry=data.industry,
        company_size=data.company_size,
        company_type=data.company_type,
        hq_location=data.hq_location,
        status=_enum_value(data.status),
        plan=_enum_value(data.plan),
        created_by_user_id=created_by_user_id,
    )
    try:
        async with session.begin_nested():
            session.add(company)
            await session.flush()
    except IntegrityError as exc:
        raise ValueError("A company with this website domain already exists.") from exc
    await session.refresh(company, ["members"])
    return company


async def register_company_for_employer(
    session: AsyncSession,
    user: User,
    *,
    company_name: str,
    company_website: str | None,
    email_verified: bool = False,
) -> Company:
    membership = await session.scalar(
        select(CompanyMember)
        .options(selectinload(CompanyMember.company).selectinload(Company.members))
        .where(CompanyMember.user_id == user.id)
    )
    if membership:
        return membership.company

    domain = normalize_domain(company_website)
    company = None
    if domain:
        company = await session.scalar(
            select(Company)
            .options(selectinload(Company.members))
            .where(Company.domain == domain)
        )
    if company is None:
        company = Company(
            name=company_name.strip(),
            domain=domain,
            website=company_website,
            status=CompanyStatus.PENDING.value,
            plan=CompanyPlan.FREE.value,
            created_by_user_id=user.id,
        )
        try:
            async with session.begin_nested():
                session.add(company)
                await session.flush()
        except IntegrityError as exc:
            raise ValueError(
                "A company with this website domain already exists; retry registration."
            ) from exc
        member_role = CompanyMemberRole.OWNER
    else:
        email_domain = user.email.rsplit("@", 1)[-1].lower()
        if not email_verified or email_domain != domain:
            raise PermissionError(
                "Your verified work email domain must match the existing company."
            )
        member_role = CompanyMemberRole.RECRUITER

    session.add(
        CompanyMember(
            user_id=user.id,
            company_id=company.id,
            member_role=member_role.value,
        )
    )
    if user.profile:
        user.profile.current_company = company.name
    await session.flush()
    return await get_company(session, str(company.id))


async def list_companies(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None,
    company_status: CompanyStatus | None,
) -> CompanyListResponse:
    filters = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(or_(Company.name.ilike(pattern), Company.domain.ilike(pattern)))
    if company_status:
        filters.append(Company.status == company_status.value)

    total = int(
        (await session.scalar(select(func.count(Company.id)).where(*filters))) or 0
    )
    companies = list(
        (
            await session.scalars(
                select(Company)
                .options(selectinload(Company.members))
                .where(*filters)
                .order_by(Company.created_at.desc(), Company.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return CompanyListResponse(
        items=[company_to_response(company) for company in companies],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


async def update_company(
    session: AsyncSession,
    company: Company,
    data: CompanyUpdateRequest,
) -> Company:
    values = data.model_dump(exclude_unset=True)
    if "website" in values:
        domain = normalize_domain(values["website"])
        if domain:
            duplicate = await session.scalar(
                select(Company).where(
                    Company.domain == domain, Company.id != company.id
                )
            )
            if duplicate:
                raise ValueError("A company with this website domain already exists.")
        company.domain = domain

    for field, value in values.items():
        if field == "website":
            company.website = value
        elif field in {"status", "plan"}:
            setattr(company, field, _enum_value(value))
        else:
            setattr(company, field, value)
    await session.flush()
    return company


async def delete_company(session: AsyncSession, company: Company) -> None:
    """Delete an empty company while protecting existing employer memberships."""
    if company.members:
        raise ValueError("Remove or reassign all employer accounts before deletion.")
    await session.delete(company)
    await session.flush()


async def list_employers(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None,
    is_active: bool | None,
    company_id: str | None,
) -> EmployerListResponse:
    filters = [User.available_roles.any(UserRole.EMPLOYER.value)]
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                User.email.ilike(pattern),
                UserProfile.display_name.ilike(pattern),
                Company.name.ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if company_id:
        filters.append(CompanyMember.company_id == company_id)

    joined = (
        select(User)
        .outerjoin(UserProfile)
        .outerjoin(CompanyMember)
        .outerjoin(Company)
        .where(*filters)
    )
    total = int(
        (
            await session.scalar(
                select(func.count(User.id))
                .select_from(User)
                .outerjoin(UserProfile)
                .outerjoin(CompanyMember)
                .outerjoin(Company)
                .where(*filters)
            )
        )
        or 0
    )
    employers = list(
        (
            await session.scalars(
                joined.options(
                    selectinload(User.profile),
                    selectinload(User.company_membership).selectinload(
                        CompanyMember.company
                    ),
                )
                .order_by(User.created_at.desc(), User.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return EmployerListResponse(
        items=[employer_to_response(user) for user in employers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


async def update_employer(
    session: AsyncSession,
    user: User,
    data: EmployerUpdateRequest,
) -> User:
    if data.is_active is not None:
        user.is_active = data.is_active

    if "company_id" in data.model_fields_set:
        await session.execute(
            delete(CompanyMember).where(CompanyMember.user_id == user.id)
        )
        if data.company_id:
            company = await get_company(session, data.company_id)
            if company is None:
                raise LookupError("Company not found.")
            session.add(
                CompanyMember(
                    user_id=user.id,
                    company_id=company.id,
                    member_role=_enum_value(data.member_role),
                )
            )
            if user.profile:
                user.profile.current_company = company.name
        elif user.profile:
            user.profile.current_company = None
    elif "member_role" in data.model_fields_set:
        membership = await session.scalar(
            select(CompanyMember).where(CompanyMember.user_id == user.id)
        )
        if membership is None:
            raise LookupError("Assign a company before setting a company role.")
        membership.member_role = _enum_value(data.member_role)

    await session.flush()
    return user


def company_to_response(company: Company) -> CompanyResponse:
    return CompanyResponse(
        id=str(company.id),
        name=company.name,
        domain=company.domain,
        website=company.website,
        industry=company.industry,
        company_size=company.company_size,
        company_type=company.company_type,
        hq_location=company.hq_location,
        status=CompanyStatus(company.status),
        plan=CompanyPlan(company.plan),
        employer_count=len(company.members),
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


def employer_to_response(user: User) -> EmployerAdminResponse:
    membership = user.company_membership
    company = membership.company if membership else None
    return EmployerAdminResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.profile.display_name if user.profile else None,
        is_active=user.is_active,
        created_at=user.created_at,
        company_id=str(company.id) if company else None,
        company_name=company.name if company else None,
        company_status=CompanyStatus(company.status) if company else None,
        member_role=(CompanyMemberRole(membership.member_role) if membership else None),
    )
