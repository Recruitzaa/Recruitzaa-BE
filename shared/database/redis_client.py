"""
shared/database/redis_client.py — Async Redis client via redis-py.
"""

from __future__ import annotations

import logging
import os

from redis.asyncio import Redis, from_url

logger = logging.getLogger(__name__)

_redis: Redis | None = None


async def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        url = os.environ["REDIS_URL"]
        _redis = from_url(url, decode_responses=True)
        logger.info("Redis client created")
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
