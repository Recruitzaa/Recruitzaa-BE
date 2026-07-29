"""Shared company enums used by the auth service."""

from enum import Enum


class CompanyStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SUSPENDED = "SUSPENDED"


class CompanyPlan(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class CompanyMemberRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    RECRUITER = "RECRUITER"
