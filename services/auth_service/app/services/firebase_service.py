"""
Auth Service — Firebase verification and token decoding.
"""

import asyncio
import logging
from typing import TypedDict

from firebase_admin import auth as firebase_auth

from shared.auth.firebase_admin import get_firebase_app

logger = logging.getLogger(__name__)


class FirebaseTokenData(TypedDict):
    uid: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


def verify_firebase_token(
    id_token: str, check_revoked: bool = True
) -> FirebaseTokenData:
    """
    Verify a Firebase ID token and return decoded claims.

    Raises HTTPException on invalid/expired tokens (called from routers via
    user_service to keep error handling centralized).
    """
    get_firebase_app()  # ensure initialized

    decoded = firebase_auth.verify_id_token(id_token, check_revoked=check_revoked)
    return FirebaseTokenData(
        uid=decoded["uid"],
        email=decoded.get("email", ""),
        email_verified=decoded.get("email_verified", False),
        name=decoded.get("name"),
        picture=decoded.get("picture"),
    )


def revoke_firebase_tokens(firebase_uid: str) -> None:
    """Revoke all refresh tokens for a Firebase user (called on logout)."""
    get_firebase_app()
    firebase_auth.revoke_refresh_tokens(firebase_uid)
    logger.info("Firebase tokens revoked for uid=%s", firebase_uid)


async def create_firebase_user(
    *, email: str, password: str, display_name: str, disabled: bool
) -> str:
    """Create an identity without blocking the FastAPI event loop."""
    get_firebase_app()
    record = await asyncio.to_thread(
        firebase_auth.create_user,
        email=email,
        password=password,
        display_name=display_name,
        disabled=disabled,
        email_verified=False,
    )
    return record.uid


async def sync_firebase_access(
    firebase_uid: str,
    *,
    primary_role: str,
    available_roles: list[str],
    is_active: bool,
) -> None:
    """Synchronize account status and informational role claims with Firebase."""
    get_firebase_app()
    await asyncio.to_thread(
        firebase_auth.set_custom_user_claims,
        firebase_uid,
        {
            "role": primary_role,
            "primary_role": primary_role,
            "available_roles": available_roles,
        },
    )
    await asyncio.to_thread(
        firebase_auth.update_user,
        firebase_uid,
        disabled=not is_active,
    )
    await asyncio.to_thread(firebase_auth.revoke_refresh_tokens, firebase_uid)


async def delete_firebase_user(firebase_uid: str) -> None:
    """Delete a Firebase identity without blocking the event loop."""
    get_firebase_app()
    await asyncio.to_thread(firebase_auth.delete_user, firebase_uid)
