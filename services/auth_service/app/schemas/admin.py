"""Admin user-management request and response schemas."""

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from shared.auth.rbac import UserRole
from shared.utils.serialization import CamelModel


class UpdateUserRolesRequest(CamelModel):
    """PUT /admin/users/{id}/roles body."""

    primary_role: UserRole
    available_roles: list[UserRole] = Field(min_length=1)

    @field_validator("available_roles")
    @classmethod
    def roles_must_be_unique(cls, roles: list[UserRole]) -> list[UserRole]:
        if len(roles) != len(set(roles)):
            raise ValueError("available_roles must not contain duplicates")
        return roles

    @model_validator(mode="after")
    def primary_role_must_be_available(self) -> "UpdateUserRolesRequest":
        if self.primary_role not in self.available_roles:
            raise ValueError("primary_role must be included in available_roles")
        return self


class UpdateUserStatusRequest(CamelModel):
    """PUT /admin/users/{id}/status body."""

    is_active: bool


class AdminUserResponse(CamelModel):
    """User identity, roles, status, and PostgreSQL profile data."""

    id: str
    email: str
    firebase_uid: str
    primary_role: UserRole
    available_roles: list[UserRole]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    display_name: str | None = None
    photo_url: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    summary: str | None = None
    notice_period: str | None = None
    is_currently_employed: bool = False
    current_company: str | None = None
    current_role: str | None = None
    current_salary: str | None = None


class AdminUserListResponse(CamelModel):
    """Paginated admin user list."""

    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
