import pytest
from pydantic import ValidationError

from services.auth_service.app.schemas.admin import UpdateUserRolesRequest
from shared.auth.rbac import UserRole


def test_role_update_requires_primary_role_to_be_available():
    with pytest.raises(ValidationError, match="primary_role must be included"):
        UpdateUserRolesRequest(
            primary_role=UserRole.EMPLOYER,
            available_roles=[UserRole.CANDIDATE],
        )


def test_role_update_rejects_duplicate_roles():
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        UpdateUserRolesRequest(
            primary_role=UserRole.CANDIDATE,
            available_roles=[UserRole.CANDIDATE, UserRole.CANDIDATE],
        )
