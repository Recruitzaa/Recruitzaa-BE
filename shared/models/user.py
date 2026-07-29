"""
shared/models/user.py — Shared AppUser Pydantic model.

Matches FE AppUser interface from web/src/types/auth.types.ts exactly.
All fields use camelCase aliases (via serialization.py) so the JSON response
matches what the FE TypeScript expects.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from shared.auth.rbac import UserRole
from shared.utils.serialization import CamelModel


class AppUser(CamelModel):
    """
    Core user model shared across all microservices.

    Serializes to camelCase JSON to match FE AppUser interface:
        id, email, role, availableRoles, displayName, photoURL, ...
    """

    # Identity
    id: str
    firebase_uid: str
    email: str

    # Roles — multi-role v3
    primary_role: UserRole  # stored in PG users.primary_role
    available_roles: list[UserRole]  # stored in PG users.available_roles[]
    active_role: UserRole | None = None  # set client-side via Launchpad; not persisted

    # Profile (from user_profiles table)
    display_name: str | None = None
    photo_url: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    summary: str | None = None

    # Employment info (AppUser.isCurrentlyEmployed etc.)
    is_currently_employed: bool = False
    current_company: str | None = None
    current_role: str | None = None
    current_salary: str | None = None
    notice_period: str | None = None

    # Skills (flat array from AppUser.skills)
    skills: list[str] = Field(default_factory=list)

    # Resume (from latest resume_versions entry)
    resume_file_name: str | None = None
    resume_file_size: str | None = None

    # Account status
    is_active: bool = True

    model_config = ConfigDict(
        populate_by_name=True,
    )

    # Convenience: FE backward-compat `role` field = active_role or primary_role
    @property
    def role(self) -> UserRole:
        return self.active_role or self.primary_role
