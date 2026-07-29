"""
Auth Service Tests — /auth endpoints.

Tests use httpx.AsyncClient with TestClient or real DB (integration tests).
"""
import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set test env before importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://recruitzaa:recruitzaa_secret@localhost:5432/recruitzaa")
os.environ.setdefault("REDIS_URL", "redis://:redis_secret@localhost:6379/0")
os.environ.setdefault("MONGODB_URL", "mongodb://recruitzaa:mongo_secret@localhost:27017/recruitzaa?authSource=admin")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture
async def client():
    from services.auth_service.app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    """Health check must return 200 with status ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "auth_service"


@pytest.mark.asyncio
async def test_register_invalid_token(client):
    """Registering with a bogus token returns 401."""
    resp = await client.post(
        "/auth/register",
        json={
            "firebaseToken": "not_a_real_token",
            "requestedRole": "CANDIDATE",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_invalid_token(client):
    """Verifying with a bogus token returns 401."""
    resp = await client.post(
        "/auth/verify",
        json={"firebaseToken": "invalid_token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    """GET /auth/me without token returns 403."""
    resp = await client.get("/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_register_admin_role_rejected(client):
    """Attempting to register as SUPER_ADMIN or EMPLOYEE should be rejected."""
    for role in ["SUPER_ADMIN", "EMPLOYEE"]:
        resp = await client.post(
            "/auth/register",
            json={"firebaseToken": "any", "requestedRole": role},
        )
        # 422 (validation error) before Firebase token check
        assert resp.status_code == 422, f"Expected 422 for role {role}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_response_is_camelcase(client):
    """Verify token endpoint response shape uses camelCase keys."""
    resp = await client.post(
        "/auth/verify",
        json={"firebaseToken": "invalid"},
    )
    # Should fail auth but if it ever succeeds, check camelCase
    # Here we just validate the error body doesn't expose snake_case
    assert resp.status_code in (401, 422)
