"""Admin user-management request and response schemas."""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

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


class AdminUserCreateRequest(UpdateUserRolesRequest):
    """Create a Firebase and Recruitzaa account from the admin portal."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=255)
    is_active: bool = True

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized


class AdminUserUpdateRequest(UpdateUserRolesRequest):
    """Atomically update roles, status, and editable PostgreSQL profile fields."""

    is_active: bool
    display_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    location: str | None = Field(None, max_length=255)
    bio: str | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


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
    skills: list[str] = Field(default_factory=list)
    resume_file_name: str | None = None
    resume_file_size: str | None = None


class AdminUserListResponse(CamelModel):
    """Paginated admin user list."""

    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
