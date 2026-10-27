-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/management_tables.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Requires: github_users table (schema/github_users.sql)

-- Enable Realtime on scraping_runs (Dashboard → Database → Replication)
-- ALTER PUBLICATION supabase_realtime ADD TABLE scraping_runs;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- scraping_runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraping_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'stopping', 'stopped', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    total_users_found INTEGER NOT NULL DEFAULT 0,
    current_country TEXT,
    countries_completed JSONB NOT NULL DEFAULT '[]'::jsonb,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    log_lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    rate_limit_remaining INTEGER,
    rate_limit_reset_at TIMESTAMPTZ,
    estimated_seconds_remaining INTEGER,
    last_error TEXT,
    celery_task_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraping_runs_status ON scraping_runs (status);
CREATE INDEX IF NOT EXISTS idx_scraping_runs_created_at ON scraping_runs (created_at DESC);

-- ---------------------------------------------------------------------------
-- github_tokens (token_value stores Fernet ciphertext from backend)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS github_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label TEXT NOT NULL DEFAULT 'default',
    token_value TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_used_at TIMESTAMPTZ,
    rate_limit_remaining INTEGER,
    rate_limit_reset_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_github_tokens_active ON github_tokens (is_active) WHERE is_active = true;

-- ---------------------------------------------------------------------------
-- scheduled_jobs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_active ON scheduled_jobs (active, next_run_at);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scraping_runs_updated ON scraping_runs;
CREATE TRIGGER trg_scraping_runs_updated
    BEFORE UPDATE ON scraping_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_github_tokens_updated ON github_tokens;
CREATE TRIGGER trg_github_tokens_updated
    BEFORE UPDATE ON github_tokens
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_scheduled_jobs_updated ON scheduled_jobs;
CREATE TRIGGER trg_scheduled_jobs_updated
    BEFORE UPDATE ON scheduled_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: admin-only (set app_metadata.role = 'admin' on Supabase Auth users)
-- ---------------------------------------------------------------------------
ALTER TABLE github_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_jobs ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN COALESCE(
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin',
        false
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- github_users
DROP POLICY IF EXISTS github_users_admin_all ON github_users;
CREATE POLICY github_users_admin_all ON github_users
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- scraping_runs
DROP POLICY IF EXISTS scraping_runs_admin_all ON scraping_runs;
CREATE POLICY scraping_runs_admin_all ON scraping_runs
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- github_tokens
DROP POLICY IF EXISTS github_tokens_admin_all ON github_tokens;
CREATE POLICY github_tokens_admin_all ON github_tokens
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- scheduled_jobs
DROP POLICY IF EXISTS scheduled_jobs_admin_all ON scheduled_jobs;
CREATE POLICY scheduled_jobs_admin_all ON scheduled_jobs
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- Service role bypasses RLS (used by FastAPI backend)
