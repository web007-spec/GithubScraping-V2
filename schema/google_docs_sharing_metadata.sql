-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/google_docs_sharing_metadata.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_by_email VARCHAR(320);
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_by_name VARCHAR(512);
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS shared_at TIMESTAMPTZ;
ALTER TABLE google_documents ADD COLUMN IF NOT EXISTS document_modified_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_google_documents_shared_by_email
    ON google_documents (shared_by_email);

CREATE INDEX IF NOT EXISTS idx_google_documents_shared_at
    ON google_documents (shared_at DESC NULLS LAST);

COMMENT ON COLUMN google_documents.shared_by_email IS
    'Contact or sharing email extracted from the public document page/content';
COMMENT ON COLUMN google_documents.shared_at IS
    'Best-effort document sharing / last-update timestamp from Google page metadata';
