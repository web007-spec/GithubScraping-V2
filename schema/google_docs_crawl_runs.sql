-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/google_docs_crawl_runs.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after schema/google_documents.sql

CREATE TABLE IF NOT EXISTS google_docs_crawl_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'stopping', 'stopped', 'completed', 'failed')),
    mode TEXT NOT NULL DEFAULT 'search'
        CHECK (mode IN ('search', 'batch_search', 'from_discovered', 'from_file')),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    discovered_count INTEGER NOT NULL DEFAULT 0,
    crawled_count INTEGER NOT NULL DEFAULT 0,
    parsed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    imported_count INTEGER NOT NULL DEFAULT 0,
    current_phase TEXT NOT NULL DEFAULT 'pending',
    log_lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_error TEXT,
    worker_pid TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_google_docs_crawl_runs_status
    ON google_docs_crawl_runs (status, created_at DESC);

DROP TRIGGER IF EXISTS trg_google_docs_crawl_runs_updated ON google_docs_crawl_runs;
CREATE TRIGGER trg_google_docs_crawl_runs_updated
    BEFORE UPDATE ON google_docs_crawl_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE google_docs_crawl_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS google_docs_crawl_runs_admin_all ON google_docs_crawl_runs;
CREATE POLICY google_docs_crawl_runs_admin_all ON google_docs_crawl_runs
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- Public read for parsed documents (explorer cards without sign-in)
DROP POLICY IF EXISTS google_documents_public_read ON google_documents;
CREATE POLICY google_documents_public_read ON google_documents
    FOR SELECT TO anon, authenticated
    USING (status = 'parsed');

COMMENT ON TABLE google_docs_crawl_runs IS
    'Background Google Docs discover/crawl jobs triggered from the admin UI';
