-- Google Docs Public Indexer schema
-- Run via Alembic migrations or apply directly to Supabase PostgreSQL

CREATE TYPE document_status AS ENUM (
    'discovered',
    'queued',
    'downloading',
    'parsed',
    'failed',
    'skipped',
    'duplicate'
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_doc_id VARCHAR(128) NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    title VARCHAR(1024),
    clean_text TEXT,
    html TEXT,
    word_count INTEGER,
    character_count INTEGER,
    language VARCHAR(16),
    sha256 VARCHAR(64),
    status document_status NOT NULL DEFAULT 'discovered',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_documents_sha256 ON documents (sha256);
CREATE INDEX IF NOT EXISTS ix_documents_status ON documents (status);
CREATE INDEX IF NOT EXISTS ix_documents_created_at ON documents (created_at);

CREATE TABLE IF NOT EXISTS links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    href TEXT NOT NULL,
    text TEXT
);

CREATE INDEX IF NOT EXISTS ix_links_document_id ON links (document_id);

CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    src TEXT NOT NULL,
    alt TEXT
);

CREATE INDEX IF NOT EXISTS ix_images_document_id ON images (document_id);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    status_code INTEGER,
    error TEXT,
    elapsed_ms INTEGER,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_crawl_logs_url ON crawl_logs (url);
CREATE INDEX IF NOT EXISTS ix_crawl_logs_timestamp ON crawl_logs (timestamp);

CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(64) NOT NULL UNIQUE,
    metric_value DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Full-text search index (optional, improves search performance)
CREATE INDEX IF NOT EXISTS ix_documents_fts ON documents
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(clean_text, '')));
