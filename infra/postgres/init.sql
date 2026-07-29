-- ============================================================
-- Recruitzaa PostgreSQL Initialization
-- Runs once when the container is first created.
-- Alembic handles all subsequent schema changes.
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Confirm init ran
DO $$
BEGIN
    RAISE NOTICE 'Recruitzaa DB initialized ✓';
END$$;
