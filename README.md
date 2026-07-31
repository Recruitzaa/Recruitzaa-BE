# Recruitzaa-BE

FastAPI backend services for Recruitzaa, using PostgreSQL for identity and
administrative data, MongoDB for role-specific profiles, Firebase
Authentication, Redis caching, and Kafka events.

## Version History

**Current Version: `v0.4.0`**

### Changelog

**[v0.4.0] - 2026-07-30** _(Branch: `fix/integration-fixes`)_

- Added atomic admin user access, status, and profile updates.
- Added complete user detail, provisioning, and PostgreSQL/MongoDB/Firebase deletion APIs.
- Added Firebase role/status synchronization, targeted Redis invalidation, active-workspace admin authorization, self-lockout protection, and last-super-admin protection.
- Added company detail and guarded deletion APIs, verified-domain membership rules, UUID validation, normalized inputs, concurrency handling, and database integrity constraints.
- Added regression tests for administrator invariants, self-service role upgrades, Firebase synchronization, company ownership, deletion safety, and validation.

**[v0.3.0] - 2026-07-30**

- Added company and employer tables, migrations, registration, administration APIs, company assignment, verification status, plans, and employer account controls.
- Added automatic Alembic upgrades to deployment startup and rebuilt containers during deployments.
- Added backend CI linting, security audit reporting, unit tests, coverage enforcement, and Docker build verification.
- Updated vulnerable dependencies, standardized Ruff formatting, and expanded authentication and Kafka tests.

**[v0.2.0] - 2026-07-29**

- Added secured admin user listing, search, role and status filtering, role management, and account activation/deactivation APIs.
- Added database-authoritative `SUPER_ADMIN` authorization and authentication cache invalidation.
- Added admin role validation and schema tests.

**[v0.1.0] - 2026-07-28**

- Added Firebase token verification, PostgreSQL users and profiles, MongoDB profile initialization, Redis token caching, Kafka registration events, and self-service authentication/profile APIs.
- Added the initial Alembic schema, Docker Compose environment, service health checks, and deployment workflow.
