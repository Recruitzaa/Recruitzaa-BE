# Recruitzaa-BE

The backend codebase for recruitZaa, built with Python (FastAPI). Integrates MongoDB & PostgreSQL for hybrid data storage, Redis for caching, Kafka for event-driven messaging, MinIO for object storage, and Firebase Admin SDK for authentication and authorization.

## Version History

**Current Version: `v0.1.0`**

### Changelog

**[v0.1.0] - 2026-07-29** _(Branch: `feat/infra-auth-service`)_

- **Infrastructure Setup**: Configured a multi-service local environment using Docker Compose including PostgreSQL (relational database), MongoDB (document storage), Redis (caching/key-value store), Kafka (messaging broker), MinIO (object storage), pgAdmin (PostgreSQL management), and Mongo Express (MongoDB management).
- **Auth Service (FastAPI)**: Implemented the Auth Service featuring Firebase authentication token verification, User CRUD endpoints, and comprehensive Role-Based Access Control (RBAC) management.
- **Shared Libraries & Utilities**: Built reusable utility layers for database connections (PostgreSQL async engine, MongoDB client, Redis client), event-driven messaging (Kafka producers and consumers with structured topic schemas), storage (MinIO helper client), caching utilities, custom HTTP exceptions, and camelCase/snake_case API request/response JSON serializers.
- **Database Migrations**: Initialized database versioning with Alembic and defined the initial user schema migration.
- **Git & Environment Hygiene**: Created `.env.example` template with secure configuration defaults, and updated `.gitignore` rules to prevent credentials, Cursor configurations, local patches, and agent/audit reports from being committed.
