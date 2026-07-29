"""
shared/database/mongo.py — Async MongoDB client via Motor.
"""
from __future__ import annotations


import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        url = os.environ["MONGODB_URL"]
        _client = AsyncIOMotorClient(url)
        logger.info("MongoDB client created")
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    """Return the recruitzaa database."""
    db_name = os.environ.get("MONGO_DB", "recruitzaa")
    return get_mongo_client()[db_name]


# FastAPI dependency
async def get_db() -> AsyncIOMotorDatabase:
    return get_mongo_db()
