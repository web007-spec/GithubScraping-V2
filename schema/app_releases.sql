-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/app_releases.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Requires: management_tables.sql (pgcrypto)

CREATE TABLE IF NOT EXISTS app_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'GitHub Scraper Client',
    description TEXT,
    install_instructions TEXT,
    file_name TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL UNIQUE,
    content_type TEXT,
    sha256 TEXT,
    is_example BOOLEAN NOT NULL DEFAULT false,
    download_count BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

-- Only one release can be the public "example" download at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_releases_single_example
    ON app_releases (is_example)
    WHERE is_example = true;

CREATE INDEX IF NOT EXISTS idx_app_releases_created_at
    ON app_releases (created_at DESC);

COMMENT ON TABLE app_releases IS
  'Distributable client builds (ZIP/extension). is_example=true is shown on login/register.';
