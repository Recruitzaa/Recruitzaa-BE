"""Company and employer-administration API schemas."""

from datetime import datetime

from pydantic import Field

from shared.models.company import CompanyMemberRole, CompanyPlan, CompanyStatus
from shared.utils.serialization import CamelModel


class EmployerCompanyRegistrationRequest(CamelModel):
    company_name: str = Field(min_length=2, max_length=255)
    company_website: str | None = Field(None, max_length=500)


class CompanyCreateRequest(CamelModel):
    name: str = Field(min_length=2, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    company_size: str | None = Field(None, max_length=80)
    company_type: str | None = Field(None, max_length=80)
    hq_location: str | None = Field(None, max_length=255)
    status: CompanyStatus = CompanyStatus.PENDING
    plan: CompanyPlan = CompanyPlan.FREE


class CompanyUpdateRequest(CamelModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    company_size: str | None = Field(None, max_length=80)
    company_type: str | None = Field(None, max_length=80)
    hq_location: str | None = Field(None, max_length=255)
    status: CompanyStatus | None = None
    plan: CompanyPlan | None = None


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
    active_jobs: int = 0
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
    active_jobs: int = 0


class EmployerListResponse(CamelModel):
    items: list[EmployerAdminResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmployerUpdateRequest(CamelModel):
    company_id: str | None = None
    member_role: CompanyMemberRole = CompanyMemberRole.RECRUITER
    is_active: bool | None = None
