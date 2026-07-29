"""
shared/auth/rbac.py — UserRole enum for all 5 Recruitzaa roles.
"""

from enum import Enum


class UserRole(str, Enum):
    CANDIDATE = "CANDIDATE"
    EMPLOYER = "EMPLOYER"
    EXPERT = "EXPERT"  # v3: expert consulting sessions
    EMPLOYEE = "EMPLOYEE"  # v3: internal employee timesheet/payroll
    SUPER_ADMIN = "SUPER_ADMIN"

    @classmethod
    def self_service_roles(cls) -> list["UserRole"]:
        """Roles a user can request at registration (public sign-up)."""
        return [cls.CANDIDATE, cls.EMPLOYER, cls.EXPERT]

    @classmethod
    def admin_only_roles(cls) -> list["UserRole"]:
        """Roles only SUPER_ADMIN can grant."""
        return [cls.EMPLOYEE, cls.SUPER_ADMIN]
