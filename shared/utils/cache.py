"""
shared/utils/cache.py — Redis cache helpers.
"""
import json
import logging
from typing import Any, TypeVar

from shared.database.redis_client import get_redis_client

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def cache_get(key: str) -> Any | None:
    try:
        redis = await get_redis_client()
        val = await redis.get(key)
        return json.loads(val) if val else None
    except Exception as exc:
        logger.warning("cache_get error key=%s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    try:
        redis = await get_redis_client()
        await redis.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("cache_set error key=%s: %s", key, exc)


async def cache_delete(key: str) -> None:
    try:
        redis = await get_redis_client()
        await redis.delete(key)
    except Exception as exc:
        logger.warning("cache_delete error key=%s: %s", key, exc)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    try:
        redis = await get_redis_client()
        keys = await redis.keys(pattern)
        if keys:
            return await redis.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("cache_delete_pattern error pattern=%s: %s", pattern, exc)
        return 0
