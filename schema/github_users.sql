-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/github_users.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor (PostgreSQL)
CREATE TABLE IF NOT EXISTS github_users (
    id BIGINT PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    name TEXT,
    location TEXT,
    company TEXT,
    email TEXT,
    bio TEXT,
    public_repos INTEGER,
    followers INTEGER,
    following INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    last_scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    country TEXT,
    blog TEXT,
    twitter_username TEXT,
    github_url TEXT,
    public_gists INTEGER,
    avatar_url TEXT,
    email_source TEXT
);

CREATE INDEX IF NOT EXISTS idx_github_users_country ON github_users (country);
CREATE INDEX IF NOT EXISTS idx_github_users_last_scraped_at ON github_users (last_scraped_at);

COMMENT ON TABLE github_users IS 'Public GitHub user profiles scraped via REST API';

-- Also run in Supabase SQL Editor (after enrichment migration):
--   schema/github_users_country_indexes.sql  -- per-country partial indexes
--   schema/country_stats.sql                 -- live counts + trigger on new rows
