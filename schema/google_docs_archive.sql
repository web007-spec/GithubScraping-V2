-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/google_docs_archive.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS search_text TEXT;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS archive_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS html TEXT;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS content_archived_at TIMESTAMPTZ;

COMMENT ON COLUMN google_documents.search_text IS
    'Normalized full document text + link text for full-text and AI search';
COMMENT ON COLUMN google_documents.archive_data IS
    'Structured archive: headings, paragraphs, lists, tables, links, images';
COMMENT ON COLUMN google_documents.html IS
    'Cleaned HTML export (optional, for re-processing)';
COMMENT ON COLUMN google_documents.content_archived_at IS
    'When full body content was last archived';

CREATE INDEX IF NOT EXISTS idx_google_documents_content_archived_at
    ON google_documents (content_archived_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_google_documents_search_fts
    ON google_documents
    USING GIN (to_tsvector('english', coalesce(search_text, coalesce(clean_text, ''))));

CREATE INDEX IF NOT EXISTS idx_google_documents_archive_data
    ON google_documents USING GIN (archive_data);

-- Replace narrow excerpt-only FTS with full-content index when present
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
