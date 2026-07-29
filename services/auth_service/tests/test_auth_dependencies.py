"""Unit tests for shared.auth.dependencies.

Covers the Redis token cache, Firebase verification failure paths, and RBAC gating.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth

from shared.auth.dependencies import (
    _cache_user,
    _get_user_from_cache,
    _token_cache_key,
    get_current_user,
    require_role,
)
from shared.auth.rbac import UserRole
from shared.models.user import AppUser

TOKEN = "a-firebase-id-token"
TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()


def make_user(**overrides) -> AppUser:
    defaults = dict(
        id="user-1",
        firebase_uid="fb-uid-1",
        email="candidate@example.com",
        primary_role=UserRole.CANDIDATE,
        available_roles=[UserRole.CANDIDATE],
    )
    defaults.update(overrides)
    return AppUser(**defaults)


def credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=TOKEN)


@asynccontextmanager
async def fake_session():
    yield MagicMock()


def test_token_cache_key_is_namespaced():
    assert _token_cache_key("abc123") == "firebase:token:abc123"


@pytest.mark.asyncio
async def test_get_user_from_cache_returns_hydrated_user():
    user = make_user()
    redis = AsyncMock()
    redis.get.return_value = user.model_dump_json()

    with patch("shared.auth.dependencies._get_redis", AsyncMock(return_value=redis)):
        cached = await _get_user_from_cache(TOKEN_HASH)

    assert cached is not None
    assert cached.id == user.id
    assert cached.email == user.email
    redis.get.assert_awaited_with(f"firebase:token:{TOKEN_HASH}")


@pytest.mark.asyncio
async def test_get_user_from_cache_returns_none_on_miss():
    redis = AsyncMock()
    redis.get.return_value = None

    with patch("shared.auth.dependencies._get_redis", AsyncMock(return_value=redis)):
        assert await _get_user_from_cache(TOKEN_HASH) is None


@pytest.mark.asyncio
async def test_get_user_from_cache_swallows_redis_errors():
    """A dead Redis must degrade to a cache miss, not raise."""
    with patch(
        "shared.auth.dependencies._get_redis",
        AsyncMock(side_effect=Exception("redis down")),
    ):
        assert await _get_user_from_cache(TOKEN_HASH) is None


@pytest.mark.asyncio
async def test_cache_user_writes_with_ttl():
    user = make_user()
    redis = AsyncMock()

    with patch("shared.auth.dependencies._get_redis", AsyncMock(return_value=redis)):
        await _cache_user(TOKEN_HASH, user, ttl=120)

    redis.setex.assert_awaited_once()
    key, ttl, payload = redis.setex.await_args.args
    assert key == f"firebase:token:{TOKEN_HASH}"
    assert ttl == 120
    assert "candidate@example.com" in payload


@pytest.mark.asyncio
async def test_cache_user_swallows_redis_errors():
    with patch(
        "shared.auth.dependencies._get_redis",
        AsyncMock(side_effect=Exception("redis down")),
    ):
        await _cache_user(TOKEN_HASH, make_user())  # must not raise


@pytest.mark.asyncio
async def test_get_current_user_short_circuits_on_cache_hit():
    user = make_user()

    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=user),
        ),
        patch("shared.auth.dependencies.get_firebase_app") as mock_app,
    ):
        result = await get_current_user(credentials())

    assert result is user
    mock_app.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        firebase_auth.RevokedIdTokenError("revoked"),
        firebase_auth.ExpiredIdTokenError("expired", None),
        ValueError("malformed token"),
    ],
    ids=["revoked", "expired", "malformed"],
)
async def test_get_current_user_rejects_bad_tokens_with_401(exc):
    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=None),
        ),
        patch("shared.auth.dependencies.get_firebase_app"),
        patch(
            "shared.auth.dependencies.firebase_auth.verify_id_token", side_effect=exc
        ),
        pytest.raises(HTTPException) as err,
    ):
        await get_current_user(credentials())

    assert err.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_500_when_db_lookup_fails():
    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=None),
        ),
        patch("shared.auth.dependencies.get_firebase_app"),
        patch(
            "shared.auth.dependencies.firebase_auth.verify_id_token",
            return_value={"uid": "fb-uid-1"},
        ),
        patch(
            "shared.database.postgres.get_db_session",
            side_effect=Exception("connection refused"),
        ),
        pytest.raises(HTTPException) as err,
    ):
        await get_current_user(credentials())

    assert err.value.status_code == 500


@pytest.mark.asyncio
async def test_get_current_user_returns_404_for_unregistered_uid():
    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=None),
        ),
        patch("shared.auth.dependencies.get_firebase_app"),
        patch(
            "shared.auth.dependencies.firebase_auth.verify_id_token",
            return_value={"uid": "fb-uid-1"},
        ),
        patch("shared.database.postgres.get_db_session", fake_session),
        patch(
            "services.auth_service.app.services.user_service.get_user_by_firebase_uid",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HTTPException) as err,
    ):
        await get_current_user(credentials())

    assert err.value.status_code == 404


@pytest.mark.asyncio
async def test_get_current_user_returns_403_for_deactivated_account():
    db_user = MagicMock(is_active=False)

    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=None),
        ),
        patch("shared.auth.dependencies.get_firebase_app"),
        patch(
            "shared.auth.dependencies.firebase_auth.verify_id_token",
            return_value={"uid": "fb-uid-1"},
        ),
        patch("shared.database.postgres.get_db_session", fake_session),
        patch(
            "services.auth_service.app.services.user_service.get_user_by_firebase_uid",
            AsyncMock(return_value=db_user),
        ),
        pytest.raises(HTTPException) as err,
    ):
        await get_current_user(credentials())

    assert err.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_caches_user_on_successful_lookup():
    db_user = MagicMock(is_active=True)
    user = make_user()

    with (
        patch(
            "shared.auth.dependencies._get_user_from_cache",
            AsyncMock(return_value=None),
        ),
        patch("shared.auth.dependencies.get_firebase_app"),
        patch(
            "shared.auth.dependencies.firebase_auth.verify_id_token",
            return_value={"uid": "fb-uid-1"},
        ),
        patch("shared.database.postgres.get_db_session", fake_session),
        patch(
            "services.auth_service.app.services.user_service.get_user_by_firebase_uid",
            AsyncMock(return_value=db_user),
        ),
        patch(
            "services.auth_service.app.services.user_service.user_to_app_user",
            return_value=user,
        ),
        patch("shared.auth.dependencies._cache_user", AsyncMock()) as mock_cache,
    ):
        result = await get_current_user(credentials())

    assert result is user
    mock_cache.assert_awaited_once_with(TOKEN_HASH, user)


@pytest.mark.asyncio
async def test_require_role_allows_matching_primary_role():
    user = make_user()
    checker = require_role(UserRole.CANDIDATE, UserRole.EMPLOYER)

    assert await checker(user) is user


@pytest.mark.asyncio
async def test_require_role_prefers_active_role_over_primary():
    """A candidate who switched into their EMPLOYER role passes an EMPLOYER gate."""
    user = make_user(
        available_roles=[UserRole.CANDIDATE, UserRole.EMPLOYER],
        active_role=UserRole.EMPLOYER,
    )
    checker = require_role(UserRole.EMPLOYER)

    assert await checker(user) is user


@pytest.mark.asyncio
async def test_require_role_rejects_mismatched_role_with_403():
    user = make_user()
    checker = require_role(UserRole.SUPER_ADMIN)

    with pytest.raises(HTTPException) as err:
        await checker(user)

    assert err.value.status_code == 403
    assert "CANDIDATE" in err.value.detail
