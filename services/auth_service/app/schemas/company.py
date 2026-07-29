"""Company and employer-administration API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from shared.models.company import CompanyMemberRole, CompanyPlan, CompanyStatus
from shared.utils.serialization import CamelModel


class EmployerCompanyRegistrationRequest(CamelModel):
    company_name: str = Field(min_length=2, max_length=255)
    company_website: str | None = Field(None, max_length=500)

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError(
                "company_name must contain at least 2 non-space characters"
            )
        return normalized


class CompanyCreateRequest(CamelModel):
    name: str = Field(min_length=2, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    company_size: str | None = Field(None, max_length=80)
    company_type: str | None = Field(None, max_length=80)
    hq_location: str | None = Field(None, max_length=255)
    status: CompanyStatus = CompanyStatus.PENDING
    plan: CompanyPlan = CompanyPlan.FREE

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("name must contain at least 2 non-space characters")
        return normalized


class CompanyUpdateRequest(CamelModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    company_size: str | None = Field(None, max_length=80)
    company_type: str | None = Field(None, max_length=80)
    hq_location: str | None = Field(None, max_length=255)
    status: CompanyStatus | None = None
    plan: CompanyPlan | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("name must contain at least 2 non-space characters")
        return normalized


class CompanyResponse(CamelModel):
    id: str
    name: str
    domain: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    company_type: str | None = None
    hq_location: str | None = None
    status: CompanyStatus
    plan: CompanyPlan
    employer_count: int = 0
    active_jobs: int | None = None
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(CamelModel):
    items: list[CompanyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmployerAdminResponse(CamelModel):
    id: str
    email: str
    display_name: str | None = None
    is_active: bool
    created_at: datetime
    company_id: str | None = None
    company_name: str | None = None
    company_status: CompanyStatus | None = None
    member_role: CompanyMemberRole | None = None
    active_jobs: int | None = None


class EmployerListResponse(CamelModel):
    items: list[EmployerAdminResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmployerUpdateRequest(CamelModel):
    company_id: UUID | None = None
    member_role: CompanyMemberRole = CompanyMemberRole.RECRUITER
    is_active: bool | None = None
