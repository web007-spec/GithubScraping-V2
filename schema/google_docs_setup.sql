-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/google_docs_setup.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN COALESCE(
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin',
        false
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ---------------------------------------------------------------------------
-- google_documents
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS google_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_doc_id VARCHAR(128) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title VARCHAR(1024),
    excerpt TEXT,
    clean_text TEXT,
    headings TEXT,
    word_count INTEGER,
    character_count INTEGER,
    language VARCHAR(16),
    sha256 VARCHAR(64),
    preview_url TEXT,
    preview_image_url TEXT,
    images_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'parsed'
        CHECK (status IN (
            'discovered', 'queued', 'downloading', 'parsed',
            'failed', 'skipped', 'duplicate'
        )),
    error_message TEXT,
    crawled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_google_documents_status
    ON google_documents (status);

CREATE INDEX IF NOT EXISTS idx_google_documents_crawled_at
    ON google_documents (crawled_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_google_documents_title
    ON google_documents (title);

CREATE INDEX IF NOT EXISTS idx_google_documents_word_count
    ON google_documents (word_count DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_google_documents_fts
    ON google_documents
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(excerpt, '')));

DROP TRIGGER IF EXISTS trg_google_documents_updated ON google_documents;
CREATE TRIGGER trg_google_documents_updated
    BEFORE UPDATE ON google_documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE google_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS google_documents_admin_all ON google_documents;
CREATE POLICY google_documents_admin_all ON google_documents
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

DROP POLICY IF EXISTS google_documents_public_read ON google_documents;
CREATE POLICY google_documents_public_read ON google_documents
    FOR SELECT TO anon, authenticated
    USING (status = 'parsed');

-- Full-content archive (AI search)
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS search_text TEXT;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS archive_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS html TEXT;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS content_archived_at TIMESTAMPTZ;

ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_by_email VARCHAR(320);
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_by_name VARCHAR(512);
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_at TIMESTAMPTZ;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS document_modified_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_google_documents_shared_by_email
    ON google_documents (shared_by_email);

CREATE INDEX IF NOT EXISTS idx_google_documents_shared_at
    ON google_documents (shared_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_google_documents_content_archived_at
    ON google_documents (content_archived_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_google_documents_search_fts
    ON google_documents
    USING GIN (to_tsvector('english', coalesce(search_text, coalesce(clean_text, ''))));

CREATE INDEX IF NOT EXISTS idx_google_documents_archive_data
    ON google_documents USING GIN (archive_data);

DROP INDEX IF EXISTS idx_google_documents_fts;
CREATE INDEX IF NOT EXISTS idx_google_documents_fts
    ON google_documents
    USING GIN (
        to_tsvector(
            'english',
            coalesce(title, '') || ' ' ||
            coalesce(search_text, coalesce(excerpt, '') || ' ' || coalesce(clean_text, ''))
        )
    );

-- ---------------------------------------------------------------------------
-- google_docs_crawl_runs
-- ---------------------------------------------------------------------------
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
