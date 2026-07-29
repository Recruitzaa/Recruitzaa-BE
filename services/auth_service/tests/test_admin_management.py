from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services.auth_service.app.models.user import User, UserProfile
from services.auth_service.app.routers.admin import _ensure_admin_invariants
from services.auth_service.app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    UpdateUserRolesRequest,
)
from services.auth_service.app.services import (
    admin_user_service,
    firebase_service,
    user_service,
)
from shared.auth.rbac import UserRole


def make_user(*, roles=None, active=True) -> User:
    user = User(
        id=uuid4(),
        firebase_uid=f"firebase-{uuid4()}",
        email=f"{uuid4()}@example.com",
        primary_role=(roles or ["CANDIDATE"])[0],
        available_roles=roles or ["CANDIDATE"],
        is_active=active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user.profile = UserProfile(display_name="Test User")
    return user


def test_admin_create_schema_normalizes_and_validates():
    request = AdminUserCreateRequest(
        email="Admin@Example.com",
        password="password123",
        display_name="  Admin User  ",
        primary_role="SUPER_ADMIN",
        available_roles=["SUPER_ADMIN"],
    )
    assert request.display_name == "Admin User"

    with pytest.raises(ValidationError):
        AdminUserCreateRequest(
            email="invalid",
            password="short",
            display_name=" ",
            primary_role="CANDIDATE",
            available_roles=["CANDIDATE"],
        )


@pytest.mark.asyncio
async def test_atomic_user_update_changes_access_and_profile():
    user = make_user()
    session = AsyncMock()
    body = AdminUserUpdateRequest(
        primary_role="EMPLOYER",
        available_roles=["CANDIDATE", "EMPLOYER"],
        is_active=False,
        display_name="Employer",
        phone="123",
        location="Hyderabad",
        bio="Hiring",
    )

    result = await admin_user_service.update_user(session, user, body)

    assert result.primary_role == "EMPLOYER"
    assert result.available_roles == ["CANDIDATE", "EMPLOYER"]
    assert result.is_active is False
    assert result.profile.display_name == "Employer"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_service_create_count_and_delete():
    session = AsyncMock()
    session.add = MagicMock()
    body = AdminUserCreateRequest(
        email="new@example.com",
        password="password123",
        display_name="New User",
        primary_role="CANDIDATE",
        available_roles=["CANDIDATE"],
    )
    created = await admin_user_service.create_user(
        session, firebase_uid="firebase-new", data=body
    )
    assert created.email == "new@example.com"
    assert created.profile.display_name == "New User"

    session.scalar.return_value = 2
    assert await admin_user_service.count_active_super_admins(session) == 2

    await admin_user_service.delete_user(session, created)
    session.delete.assert_awaited_once_with(created)


@pytest.mark.asyncio
async def test_admin_list_and_legacy_mutations():
    listed_user = make_user(roles=["EMPLOYER"])
    session = AsyncMock()
    session.scalar.return_value = 1
    scalar_result = MagicMock()
    scalar_result.all.return_value = [listed_user]
    session.scalars.return_value = scalar_result

    page = await admin_user_service.list_users(
        session,
        page=1,
        page_size=20,
        search="test",
        role=UserRole.EMPLOYER,
        is_active=True,
    )
    assert page.total == 1
    assert page.items[0].id == str(listed_user.id)
    assert page.has_next is False

    roles = UpdateUserRolesRequest(
        primary_role="CANDIDATE",
        available_roles=["CANDIDATE"],
    )
    await admin_user_service.update_user_roles(session, listed_user, roles)
    await admin_user_service.update_user_status(session, listed_user, is_active=False)
    assert listed_user.primary_role == "CANDIDATE"
    assert listed_user.is_active is False


@pytest.mark.asyncio
async def test_mongo_profile_read_and_delete():
    candidate_profiles = MagicMock(
        find_one=AsyncMock(return_value={"skills_flat": ["Python"]}),
        delete_many=AsyncMock(),
    )
    employer_profiles = MagicMock(delete_many=AsyncMock())
    database = MagicMock(
        candidate_profiles=candidate_profiles,
        employer_profiles=employer_profiles,
    )
    with patch("shared.database.mongo.get_mongo_db", return_value=database):
        assert await admin_user_service.load_mongo_profile("user-1") == {
            "skills_flat": ["Python"]
        }
        await admin_user_service.delete_mongo_profile("user-1")
    candidate_profiles.delete_many.assert_awaited_once_with({"user_id": "user-1"})
    employer_profiles.delete_many.assert_awaited_once_with({"user_id": "user-1"})


@pytest.mark.asyncio
async def test_existing_user_registration_adds_requested_self_service_role():
    user = make_user(roles=["CANDIDATE"])
    session = AsyncMock()
    with patch.object(
        user_service,
        "get_user_by_firebase_uid",
        AsyncMock(return_value=user),
    ):
        result = await user_service.create_user(
            session,
            firebase_uid=user.firebase_uid,
            email=user.email,
            requested_role=UserRole.EMPLOYER,
        )
    assert result.available_roles == ["CANDIDATE", "EMPLOYER"]
    session.flush.assert_awaited_once()


def test_admin_response_includes_mongo_projection():
    user = make_user()
    response = admin_user_service.user_to_admin_response(
        user,
        {
            "skills_flat": ["Python"],
            "resume_versions": [{"file_name": "resume.pdf", "file_size": "10 KB"}],
        },
    )
    assert response.skills == ["Python"]
    assert response.resume_file_name == "resume.pdf"
    assert response.resume_file_size == "10 KB"


@pytest.mark.asyncio
async def test_admin_invariants_prevent_self_lockout():
    admin = make_user(roles=["SUPER_ADMIN"])
    with pytest.raises(HTTPException) as error:
        await _ensure_admin_invariants(
            AsyncMock(),
            actor=admin,
            target=admin,
            next_roles=["CANDIDATE"],
            next_is_active=True,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_invariants_prevent_removing_last_admin():
    actor = make_user(roles=["SUPER_ADMIN"])
    target = make_user(roles=["SUPER_ADMIN"])
    with (
        patch.object(
            admin_user_service,
            "count_active_super_admins",
            AsyncMock(return_value=1),
        ),
        pytest.raises(HTTPException) as error,
    ):
        await _ensure_admin_invariants(
            AsyncMock(),
            actor=actor,
            target=target,
            next_roles=["CANDIDATE"],
            next_is_active=True,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_invariants_allow_safe_update():
    actor = make_user(roles=["SUPER_ADMIN"])
    target = make_user(roles=["CANDIDATE"])
    await _ensure_admin_invariants(
        AsyncMock(),
        actor=actor,
        target=target,
        next_roles=["EMPLOYER"],
        next_is_active=True,
    )


@pytest.mark.asyncio
async def test_firebase_lifecycle_helpers_run_off_thread():
    record = MagicMock(uid="firebase-1")
    with (
        patch.object(firebase_service, "get_firebase_app"),
        patch.object(
            firebase_service.asyncio,
            "to_thread",
            AsyncMock(side_effect=[record, None, None, None, None]),
        ) as to_thread,
    ):
        uid = await firebase_service.create_firebase_user(
            email="user@example.com",
            password="password123",
            display_name="User",
            disabled=False,
        )
        await firebase_service.sync_firebase_access(
            uid,
            primary_role=UserRole.EMPLOYER.value,
            available_roles=[UserRole.EMPLOYER.value],
            is_active=False,
        )
        await firebase_service.delete_firebase_user(uid)

    assert uid == "firebase-1"
    assert to_thread.await_count == 5
