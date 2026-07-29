from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.auth_service.app.models.user import Company, User, UserProfile
from services.auth_service.app.routers import admin, companies
from services.auth_service.app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    UpdateUserRolesRequest,
    UpdateUserStatusRequest,
)
from services.auth_service.app.schemas.company import (
    CompanyCreateRequest,
    CompanyUpdateRequest,
    EmployerCompanyRegistrationRequest,
    EmployerUpdateRequest,
)
from services.auth_service.app.services import admin_user_service, company_service


def user(*, roles=None, active=True) -> User:
    result = User(
        id=uuid4(),
        firebase_uid=f"firebase-{uuid4()}",
        email="admin@example.com",
        primary_role=(roles or ["SUPER_ADMIN"])[0],
        available_roles=roles or ["SUPER_ADMIN"],
        is_active=active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    result.profile = UserProfile(display_name="Admin")
    return result


def company(*, members=None) -> Company:
    result = Company(
        id=uuid4(),
        name="Acme",
        domain="acme.example",
        status="PENDING",
        plan="FREE",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    result.members = members or []
    return result


@pytest.mark.asyncio
async def test_require_super_admin_requires_active_workspace():
    db_user = user()
    with patch.object(
        admin.user_service,
        "get_user_by_id",
        AsyncMock(return_value=db_user),
    ):
        with pytest.raises(HTTPException) as error:
            await admin.require_super_admin(
                MagicMock(id=str(db_user.id)),
                AsyncMock(),
                active_role="EMPLOYER",
            )
        assert error.value.status_code == 403

        assert (
            await admin.require_super_admin(
                MagicMock(id=str(db_user.id)),
                AsyncMock(),
                active_role="SUPER_ADMIN",
            )
            is db_user
        )


@pytest.mark.asyncio
async def test_user_lookup_and_targeted_cache_helpers():
    redis = AsyncMock()
    redis.smembers.return_value = {"firebase:token:one"}
    with patch.object(admin, "get_redis_client", AsyncMock(return_value=redis)):
        await admin._invalidate_auth_cache("user-1")
    redis.delete.assert_any_await("firebase:token:one")
    redis.delete.assert_any_await("firebase:user:user-1:tokens")

    with (
        patch.object(
            admin.user_service, "get_user_by_id", AsyncMock(return_value=None)
        ),
        pytest.raises(HTTPException) as error,
    ):
        await admin._get_target_user(AsyncMock(), uuid4())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_routes_delegate_filters():
    actor = user()
    with patch.object(
        admin_user_service, "list_users", AsyncMock(return_value="users")
    ):
        assert (
            await admin.list_users(
                actor,
                AsyncMock(),
                page=2,
                page_size=10,
                search="x",
                role=None,
                is_active=False,
            )
            == "users"
        )
    with patch.object(
        company_service,
        "list_companies",
        AsyncMock(return_value="companies"),
    ):
        assert (
            await admin.list_companies(
                actor,
                AsyncMock(),
                page=1,
                page_size=20,
                search=None,
                company_status=None,
            )
            == "companies"
        )
    with patch.object(
        company_service,
        "list_employers",
        AsyncMock(return_value="employers"),
    ):
        assert (
            await admin.list_employers(
                actor,
                AsyncMock(),
                page=1,
                page_size=20,
                search=None,
                is_active=None,
                company_id=None,
            )
            == "employers"
        )


@pytest.mark.asyncio
async def test_create_and_get_admin_user():
    actor = user()
    created = user(roles=["CANDIDATE"])
    body = AdminUserCreateRequest(
        email="person@example.com",
        password="password123",
        display_name="Person",
        primary_role="CANDIDATE",
        available_roles=["CANDIDATE"],
    )
    with (
        patch.object(
            admin.firebase_service,
            "create_firebase_user",
            AsyncMock(return_value=created.firebase_uid),
        ),
        patch.object(admin.firebase_service, "sync_firebase_access", AsyncMock()),
        patch.object(
            admin_user_service,
            "create_user",
            AsyncMock(return_value=created),
        ),
    ):
        response = await admin.create_user(body, actor, AsyncMock())
    assert response.email == created.email

    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=created)),
        patch.object(
            admin_user_service,
            "load_mongo_profile",
            AsyncMock(return_value={"skills_flat": ["Python"]}),
        ),
    ):
        detail = await admin.get_user_detail(created.id, actor, AsyncMock())
    assert detail.skills == ["Python"]


@pytest.mark.asyncio
async def test_atomic_update_and_delete_routes():
    actor = user()
    target = user(roles=["CANDIDATE"])
    body = AdminUserUpdateRequest(
        primary_role="EMPLOYER",
        available_roles=["EMPLOYER"],
        is_active=True,
        display_name="Employer",
    )
    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=target)),
        patch.object(admin, "_ensure_admin_invariants", AsyncMock()),
        patch.object(admin.firebase_service, "sync_firebase_access", AsyncMock()),
        patch.object(
            admin_user_service,
            "update_user",
            AsyncMock(return_value=target),
        ),
        patch.object(admin, "_invalidate_auth_cache", AsyncMock()),
    ):
        response = await admin.update_user(target.id, body, actor, AsyncMock())
    assert response.id == str(target.id)

    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=target)),
        patch.object(admin, "_ensure_admin_invariants", AsyncMock()),
        patch.object(admin_user_service, "delete_mongo_profile", AsyncMock()),
        patch.object(admin.firebase_service, "delete_firebase_user", AsyncMock()),
        patch.object(admin_user_service, "delete_user", AsyncMock()),
        patch.object(admin, "_invalidate_auth_cache", AsyncMock()),
    ):
        response = await admin.delete_user(target.id, actor, AsyncMock())
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_legacy_role_and_status_routes_remain_consistent():
    actor = user()
    target = user(roles=["CANDIDATE"])
    roles = UpdateUserRolesRequest(
        primary_role="EMPLOYER", available_roles=["EMPLOYER"]
    )
    status_body = UpdateUserStatusRequest(is_active=False)
    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=target)),
        patch.object(admin, "_ensure_admin_invariants", AsyncMock()),
        patch.object(admin.firebase_service, "sync_firebase_access", AsyncMock()),
        patch.object(admin, "_invalidate_auth_cache", AsyncMock()),
    ):
        role_response = await admin.update_user_roles(
            target.id, roles, actor, AsyncMock()
        )
        status_response = await admin.update_user_status(
            target.id, status_body, actor, AsyncMock()
        )
    assert role_response.primary_role == "EMPLOYER"
    assert status_response.is_active is False


@pytest.mark.asyncio
async def test_delete_self_is_rejected():
    actor = user()
    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=actor)),
        pytest.raises(HTTPException) as error,
    ):
        await admin.delete_user(actor.id, actor, AsyncMock())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_company_detail_update_and_delete_routes():
    actor = user()
    record = company()
    with patch.object(company_service, "get_company", AsyncMock(return_value=record)):
        detail = await admin.get_company(record.id, actor, AsyncMock())
    assert detail.id == str(record.id)

    body = CompanyUpdateRequest(name="Acme Updated")
    with (
        patch.object(company_service, "get_company", AsyncMock(return_value=record)),
        patch.object(company_service, "update_company", AsyncMock(return_value=record)),
    ):
        updated = await admin.update_company(record.id, body, actor, AsyncMock())
    assert updated.name == "Acme"

    with (
        patch.object(company_service, "get_company", AsyncMock(return_value=record)),
        patch.object(company_service, "delete_company", AsyncMock()),
    ):
        response = await admin.delete_company(record.id, actor, AsyncMock())
    assert response.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["get", "update", "delete"])
async def test_company_routes_return_not_found(operation):
    record_id = uuid4()
    actor = user()
    with (
        patch.object(company_service, "get_company", AsyncMock(return_value=None)),
        pytest.raises(HTTPException) as error,
    ):
        if operation == "get":
            await admin.get_company(record_id, actor, AsyncMock())
        elif operation == "update":
            await admin.update_company(
                record_id,
                CompanyUpdateRequest(name="Updated"),
                actor,
                AsyncMock(),
            )
        else:
            await admin.delete_company(record_id, actor, AsyncMock())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_update_employer_success_and_validation():
    actor = user()
    target = user(roles=["EMPLOYER"])
    target.company_membership = None
    body = EmployerUpdateRequest(is_active=False)
    session = AsyncMock()
    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=target)),
        patch.object(company_service, "update_employer", AsyncMock()),
        patch.object(
            admin.user_service,
            "get_user_by_id",
            AsyncMock(return_value=target),
        ),
        patch.object(admin.firebase_service, "sync_firebase_access", AsyncMock()),
        patch.object(admin, "_invalidate_auth_cache", AsyncMock()),
    ):
        response = await admin.update_employer(target.id, body, actor, session)
    assert response.id == str(target.id)

    non_employer = user(roles=["CANDIDATE"])
    with (
        patch.object(admin, "_get_target_user", AsyncMock(return_value=non_employer)),
        pytest.raises(HTTPException) as error,
    ):
        await admin.update_employer(non_employer.id, body, actor, AsyncMock())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_company_registration_maps_ownership_errors():
    employer = user(roles=["EMPLOYER"])
    body = EmployerCompanyRegistrationRequest(
        company_name="Acme", company_website="https://acme.example"
    )
    with (
        patch.object(
            company_service,
            "register_company_for_employer",
            AsyncMock(side_effect=PermissionError("domain mismatch")),
        ),
        pytest.raises(HTTPException) as error,
    ):
        await companies.register_employer_company(
            body,
            companies.EmployerContext(user=employer, email_verified=False),
            AsyncMock(),
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_create_company_maps_duplicate_domain():
    body = CompanyCreateRequest(name="Acme", website="https://acme.example")
    with (
        patch.object(
            company_service,
            "create_company",
            AsyncMock(side_effect=ValueError("duplicate")),
        ),
        pytest.raises(HTTPException) as error,
    ):
        await admin.create_company(body, user(), AsyncMock())
    assert error.value.status_code == 409
