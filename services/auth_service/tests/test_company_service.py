from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.auth_service.app.models.user import (
    Company,
    CompanyMember,
    User,
    UserProfile,
)
from services.auth_service.app.schemas.company import (
    CompanyCreateRequest,
    CompanyUpdateRequest,
    EmployerUpdateRequest,
)
from services.auth_service.app.services.company_service import (
    company_to_response,
    create_company,
    delete_company,
    employer_to_response,
    list_companies,
    list_employers,
    normalize_domain,
    register_company_for_employer,
    update_company,
    update_employer,
)
from shared.models.company import CompanyStatus


def test_normalize_domain_accepts_full_url():
    assert normalize_domain("https://www.Example.com/about") == "example.com"


def test_normalize_domain_accepts_bare_domain():
    assert normalize_domain("jobs.example.com") == "jobs.example.com"


def test_normalize_domain_handles_missing_website():
    assert normalize_domain(None) is None


@pytest.mark.parametrize(
    "website",
    ["company", "ftp://example.com", "https://", "https://example..com"],
)
def test_normalize_domain_rejects_invalid_websites(website):
    with pytest.raises(ValueError):
        normalize_domain(website)


def test_company_name_rejects_whitespace():
    with pytest.raises(ValidationError):
        CompanyCreateRequest(name="  ")


@pytest.mark.asyncio
async def test_existing_company_requires_matching_work_email():
    company = Company(
        id=uuid4(),
        name="Example",
        domain="example.com",
        status="VERIFIED",
        plan="FREE",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user = User(
        id=uuid4(),
        email="attacker@other.com",
        firebase_uid="firebase",
        primary_role="EMPLOYER",
        available_roles=["EMPLOYER"],
        is_active=True,
    )
    session = AsyncMock()
    session.scalar.side_effect = [None, company]

    with pytest.raises(PermissionError):
        await register_company_for_employer(
            session,
            user,
            company_name="Example",
            company_website="https://example.com",
        )


@pytest.mark.asyncio
async def test_verified_matching_work_email_can_join_existing_company():
    company = Company(
        id=uuid4(),
        name="Example",
        domain="example.com",
        status="VERIFIED",
        plan="FREE",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    company.members = []
    user = User(
        id=uuid4(),
        email="recruiter@example.com",
        firebase_uid="firebase",
        primary_role="EMPLOYER",
        available_roles=["EMPLOYER"],
        is_active=True,
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [None, company, company]

    result = await register_company_for_employer(
        session,
        user,
        company_name="Example",
        company_website="https://example.com",
        email_verified=True,
    )

    assert result is company
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_company_with_members_cannot_be_deleted():
    company = Company(name="Example", status="PENDING", plan="FREE")
    company.members = [CompanyMember(user_id=uuid4(), company_id=uuid4())]
    with pytest.raises(ValueError):
        await delete_company(AsyncMock(), company)


@pytest.mark.asyncio
async def test_empty_company_can_be_deleted():
    company = Company(name="Example", status="PENDING", plan="FREE")
    company.members = []
    session = AsyncMock()
    await delete_company(session, company)
    session.delete.assert_awaited_once_with(company)
    session.flush.assert_awaited_once()


def nested_context():
    context = MagicMock()
    context.__aenter__ = AsyncMock()
    context.__aexit__ = AsyncMock(return_value=False)
    return context


@pytest.mark.asyncio
async def test_create_update_and_serialize_company():
    session = AsyncMock()
    session.add = MagicMock()
    session.begin_nested = MagicMock(return_value=nested_context())
    body = CompanyCreateRequest(
        name=" Acme ",
        website=None,
        status="PENDING",
        plan="FREE",
    )
    created = await create_company(session, body)
    assert created.name == "Acme"
    created.id = uuid4()
    created.created_at = datetime.now(UTC)
    created.updated_at = datetime.now(UTC)
    assert company_to_response(created).employer_count == 0

    update = CompanyUpdateRequest(
        name="Acme Global",
        website="https://www.acme.example",
        status="VERIFIED",
        plan="PRO",
    )
    session.scalar.return_value = None
    updated = await update_company(session, created, update)
    assert updated.domain == "acme.example"
    assert updated.status == "VERIFIED"


@pytest.mark.asyncio
async def test_list_companies_returns_pagination():
    record = Company(
        id=uuid4(),
        name="Acme",
        domain="acme.example",
        status="VERIFIED",
        plan="PRO",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    record.members = []
    session = AsyncMock()
    session.scalar.return_value = 1
    result = MagicMock()
    result.all.return_value = [record]
    session.scalars.return_value = result
    page = await list_companies(
        session,
        page=1,
        page_size=20,
        search="Acme",
        company_status=CompanyStatus.VERIFIED,
    )
    assert page.total == 1
    assert page.total_pages == 1


@pytest.mark.asyncio
async def test_list_update_and_serialize_employer():
    record = User(
        id=uuid4(),
        email="owner@acme.example",
        firebase_uid="firebase",
        primary_role="EMPLOYER",
        available_roles=["EMPLOYER"],
        is_active=True,
        created_at=datetime.now(UTC),
    )
    record.profile = UserProfile(display_name="Owner")
    record.company_membership = None
    session = AsyncMock()
    session.scalar.return_value = 1
    scalar_result = MagicMock()
    scalar_result.all.return_value = [record]
    session.scalars.return_value = scalar_result
    page = await list_employers(
        session,
        page=1,
        page_size=20,
        search="Owner",
        is_active=True,
        company_id=None,
    )
    assert page.items[0].display_name == "Owner"
    assert employer_to_response(record).company_id is None

    update = EmployerUpdateRequest(company_id=None, is_active=False)
    await update_employer(session, record, update)
    assert record.is_active is False
    assert record.profile.current_company is None
