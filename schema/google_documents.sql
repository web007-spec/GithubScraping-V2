-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/google_documents.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after management_tables.sql

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

COMMENT ON TABLE google_documents IS
    'Public Google Docs discovered and indexed for the Docs explorer UI';

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
