.PHONY: up down logs ps build migrate test shell-db shell-redis lint fmt check

# ─── Infrastructure ──────────────────────────────────────────────────────────

## Start all infra + services (build if needed)
up:
	docker compose up -d --build
	@echo ""
	@echo "✅ Recruitzaa infra is up!"
	@echo "   PostgreSQL  : localhost:5432"
	@echo "   MongoDB     : localhost:27017"
	@echo "   Redis       : localhost:6379"
	@echo "   Kafka       : localhost:9092"
	@echo "   MinIO API   : localhost:9000"
	@echo "   MinIO UI    : http://localhost:9001"
	@echo "   Kafka UI    : http://localhost:8085"
	@echo "   Auth API    : http://localhost:8001"

## Start only infrastructure (no app services)
infra:
	docker compose up -d postgres mongo redis kafka minio
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 5
	@docker compose ps

## Stop all containers
down:
	docker compose down

## Stop + remove volumes (DESTRUCTIVE)
down-volumes:
	docker compose down -v
	@echo "⚠️  All data volumes removed"

## Tail logs (all services or specific: make logs s=auth-service)
logs:
ifdef s
	docker compose logs -f $(s)
else
	docker compose logs -f
endif

## Show container status
ps:
	docker compose ps

## Rebuild a specific service: make build s=auth-service
build:
ifdef s
	docker compose build $(s)
else
	docker compose build
endif

# ─── Database Migrations ─────────────────────────────────────────────────────

## Run Alembic migrations for auth service
migrate:
	cd services/auth_service && \
		PYTHONPATH=/home/sumanth/Recruitzaa-BE \
		/home/sumanth/Recruitzaa-BE/.venv/bin/alembic upgrade head
	@echo "✅ Auth service migrations applied"

## Create a new Alembic migration: make revision msg="add_expert_tables"
revision:
	cd services/auth_service && \
		PYTHONPATH=/home/sumanth/Recruitzaa-BE \
		/home/sumanth/Recruitzaa-BE/.venv/bin/alembic revision --autogenerate -m "$(msg)"

## Show migration history
history:
	cd services/auth_service && \
		PYTHONPATH=/home/sumanth/Recruitzaa-BE \
		/home/sumanth/Recruitzaa-BE/.venv/bin/alembic history

# ─── Shell Access ─────────────────────────────────────────────────────────────

## psql shell
shell-db:
	docker compose exec postgres psql -U recruitzaa -d recruitzaa

## Redis CLI
shell-redis:
	docker compose exec redis redis-cli -a redis_secret

## Mongo shell
shell-mongo:
	docker compose exec mongo mongosh -u recruitzaa -p mongo_secret --authenticationDatabase admin recruitzaa

## Bash into a service: make shell s=auth-service
shell:
	docker compose exec $(s) /bin/bash

# ─── MinIO Bucket Setup ───────────────────────────────────────────────────────

## Create required MinIO buckets
minio-setup:
	@echo "Setting up MinIO buckets..."
	docker run --rm --network recruitzaa-be_recruitzaa-net \
		--entrypoint sh minio/mc:latest -c "\
		mc alias set local http://minio:9000 minioadmin minio_secret && \
		mc mb --ignore-existing local/resumes && \
		mc mb --ignore-existing local/profile-photos && \
		mc mb --ignore-existing local/documents && \
		echo 'Buckets created'"

# ─── Testing ──────────────────────────────────────────────────────────────────

## Run all tests
test:
	PYTHONPATH=/home/sumanth/Recruitzaa-BE \
	.venv/bin/pytest services/auth_service/tests/ -v --tb=short

## Run tests with coverage
test-cov:
	PYTHONPATH=/home/sumanth/Recruitzaa-BE \
	.venv/bin/pytest services/auth_service/tests/ -v --cov=app --cov-report=term-missing

# ─── Code Quality ─────────────────────────────────────────────────────────────

## Run ruff linter
lint:
	.venv/bin/ruff check shared/ services/

## Fix linting issues automatically
fmt:
	.venv/bin/ruff check --fix shared/ services/
	.venv/bin/ruff format shared/ services/

## Full check (lint + format check)
check:
	.venv/bin/ruff check shared/ services/
	.venv/bin/ruff format --check shared/ services/

# ─── Dev Setup ────────────────────────────────────────────────────────────────

## Create .env from example if not exists
env:
	@[ -f .env ] && echo ".env already exists — skipping" || (cp .env.example .env && echo "✅ .env created from .env.example — fill in your secrets!")

## Create secrets directory
secrets-dir:
	@mkdir -p secrets
	@echo "Place firebase-sa.json in ./secrets/"

## Install dev dependencies (shared + auth service) into a venv
venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r services/auth_service/requirements.txt
	.venv/bin/pip install ruff pytest pytest-asyncio httpx pytest-cov
	@echo "✅ venv ready — activate with: source .venv/bin/activate"
