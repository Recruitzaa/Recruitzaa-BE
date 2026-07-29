#!/bin/sh
set -eu

cd /app/services/auth_service
alembic upgrade head

exec uvicorn services.auth_service.app.main:app --host 0.0.0.0 --port 8001
