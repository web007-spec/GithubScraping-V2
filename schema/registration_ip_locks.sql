-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/registration_ip_locks.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor to prevent multiple account registrations
-- from the same detected client IP address.

CREATE TABLE IF NOT EXISTS registration_ip_locks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_ip TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    user_id UUID,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'created')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registration_ip_locks_created_at
    ON registration_ip_locks (created_at DESC);

ALTER TABLE registration_ip_locks ENABLE ROW LEVEL SECURITY;

-- The FastAPI service-role client manages this table. Do not expose it to anon users.
