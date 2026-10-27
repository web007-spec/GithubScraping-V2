-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/extension_join_requests.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor (same project as github_users).

CREATE TABLE IF NOT EXISTS extension_join_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_ip TEXT NOT NULL UNIQUE,
    operator_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_extension_join_requests_status
    ON extension_join_requests (status, requested_at DESC);

COMMENT ON TABLE extension_join_requests IS
    'Chrome extension server join requests — approved IPs may read github_users via API';
