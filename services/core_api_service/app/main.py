"""
Core API Service — FastAPI application entry point.

Handles Jobs, Applications, Kanban, and Candidate Profiles.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.auth.firebase_admin import get_firebase_app
from .routers import applications, jobs, kanban, profile, resume

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("APP_ENV") == "development" else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Core API Service starting up...")

    # 1. Firebase Admin SDK
    try:
        get_firebase_app()
        logger.info("✅ Firebase Admin SDK initialized")
    except Exception as exc:
        logger.warning("⚠️  Firebase init failed: %s", exc)

    # 2. Redis connection
    try:
        from shared.database.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as exc:
        logger.warning("⚠️  Redis connection failed: %s", exc)

    # 3. MongoDB connection
    try:
        from shared.database.mongo import get_mongo_client

        client = get_mongo_client()
        await client.admin.command("ping")
        logger.info("✅ MongoDB connected")
    except Exception as exc:
        logger.warning("⚠️  MongoDB connection failed: %s", exc)

    # 4. PostgreSQL connection
    try:
        from sqlalchemy import text
        from shared.database.postgres import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connected")
    except Exception as exc:
        logger.warning("⚠️  PostgreSQL connection failed: %s", exc)

    logger.info("✅ Core API Service ready on :8002")
    yield

    logger.info("🛑 Core API Service shutting down...")
    from shared.database.redis_client import close_redis

    await close_redis()
    try:
        import shared.messaging.kafka_producer as kp
        if kp._producer:
            await kp._producer.stop()
    except Exception:
        pass
    logger.info("✅ Core API Service shutdown complete")


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Recruitzaa — Core API Service",
    description="Jobs, Applications, Kanban Board, and Candidate Profiles.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include Routers ─────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(kanban.router)
app.include_router(profile.router)
app.include_router(resume.router)


# ─── Health Check & Root ──────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok", "service": "core_api_service", "version": "1.0.0"})


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Recruitzaa Core API Service v1", "docs": "/docs"}
