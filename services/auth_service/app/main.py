"""
Auth Service — FastAPI application entry point.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.auth_service.app.routers import admin, auth
from shared.auth.firebase_admin import get_firebase_app

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("APP_ENV") == "development" else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup/shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("🚀 Auth Service starting up...")

    # Initialize Firebase Admin SDK
    try:
        get_firebase_app()
        logger.info("✅ Firebase Admin SDK initialized")
    except Exception as exc:
        logger.warning("⚠️  Firebase init failed (will retry on first request): %s", exc)

    # Verify PostgreSQL connection
    try:
        from sqlalchemy import text

        from shared.database.postgres import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connected")
    except Exception as exc:
        logger.error("❌ PostgreSQL connection failed: %s", exc)

    # Verify Redis connection
    try:
        from shared.database.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as exc:
        logger.warning("⚠️  Redis connection failed (cache disabled): %s", exc)

    # Verify MongoDB connection
    try:
        from shared.database.mongo import get_mongo_client

        client = get_mongo_client()
        await client.admin.command("ping")
        logger.info("✅ MongoDB connected")
    except Exception as exc:
        logger.warning("⚠️  MongoDB connection failed: %s", exc)

    logger.info("✅ Auth Service ready on :8001")
    yield

    # ── Shutdown ──
    logger.info("🛑 Auth Service shutting down...")
    from shared.database.redis_client import close_redis

    await close_redis()
    # Close global producer if open
    try:
        import shared.messaging.kafka_producer as kp

        if kp._producer:
            await kp._producer.stop()
    except Exception:
        pass
    logger.info("✅ Auth Service shutdown complete")


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Recruitzaa — Auth Service",
    description=(
        "Authentication, registration, and user profile management for all 5 roles."
    ),
    version="3.0.0",
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

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok", "service": "auth_service", "version": "3.0.0"})


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Recruitzaa Auth Service v3", "docs": "/docs"}
