"""
Auth Service Pydantic schemas — request/response shapes.

All responses extend CamelModel → camelCase JSON output matching FE AppUser interface.
"""

from pydantic import Field, field_validator

from shared.auth.rbac import UserRole
from shared.utils.serialization import CamelModel

# ─── Request Schemas ──────────────────────────────────────────────────────────


class RegisterRequest(CamelModel):
    """POST /auth/register body."""

    firebase_token: str = Field(..., description="Firebase ID token from client SDK")
    requested_role: UserRole = Field(
        UserRole.CANDIDATE,
        description="Role requested at signup. EMPLOYEE/SUPER_ADMIN not allowed.",
    )
    display_name: str | None = None

    @field_validator("requested_role", mode="before")
    @classmethod
    def validate_self_service_role(cls, v: str) -> str:
        admin_only = {r.value for r in UserRole.admin_only_roles()}
        if str(v) in admin_only:
            raise ValueError(f"{v} cannot be self-registered. Contact a SUPER_ADMIN.")
        return v


class VerifyTokenRequest(CamelModel):
    """POST /auth/verify body."""

    firebase_token: str


class UpdateProfileRequest(CamelModel):
    """PUT /auth/me body."""

    display_name: str | None = None
    phone: str | None = None
    photo_url: str | None = None
    location: str | None = None
    bio: str | None = None
    summary: str | None = None
    notice_period: str | None = None
    is_currently_employed: bool | None = None
    current_company: str | None = None
    current_role: str | None = None
    current_salary: str | None = None


class FCMTokenRequest(CamelModel):
    """POST /auth/fcm-token body."""

    token: str
    platform: str = Field("web", pattern="^(web|android|ios)$")


# ─── Response Schemas ─────────────────────────────────────────────────────────


class AppUserResponse(CamelModel):
    """
    Full AppUser response — camelCase to match FE TypeScript AppUser interface.

    FE reads:
        appUser.role              → effective role (active_role or primary_role)
        appUser.availableRoles    → list for Launchpad cards
        appUser.displayName       → shown in nav
        appUser.isCurrentlyEmployed → employment badge
        ...etc
    """

    # Identity
    id: str
    email: str
    firebase_uid: str

    # Roles — THE CRITICAL FIELDS for Launchpad
    role: UserRole  # backward-compat: active or primary role
    available_roles: list[UserRole]  # → "availableRoles" in JSON

    # Profile
    display_name: str | None = None
    photo_url: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    summary: str | None = None

    # Employment
    is_currently_employed: bool = False
    current_company: str | None = None
    current_role: str | None = None
    current_salary: str | None = None
    notice_period: str | None = None

    # Skills
    skills: list[str] = Field(default_factory=list)

    # Resume
    resume_file_name: str | None = None
    resume_file_size: str | None = None

    # Account
    is_active: bool = True


class AuthResponse(CamelModel):
    """Wrapper returned from register/verify/me endpoints."""

    user: AppUserResponse
    message: str = "OK"


class LogoutResponse(CamelModel):
    message: str = "Logged out successfully"
