-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/extension_contacts.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

CREATE TABLE IF NOT EXISTS extension_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_login TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    all_emails TEXT[] NOT NULL DEFAULT '{}',
    location TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    email_source TEXT NOT NULL DEFAULT '',
    total_contributions INTEGER NOT NULL DEFAULT 0,
    public_contributions INTEGER NOT NULL DEFAULT 0,
    owner_ip TEXT NOT NULL DEFAULT '',
    contact_ip TEXT NOT NULL DEFAULT '',
    saved_ip TEXT NOT NULL DEFAULT '',
    emails_sent_count INTEGER NOT NULL DEFAULT 0,
    outreach_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (outreach_status IN ('pending', 'queued', 'sent', 'read', 'replied')),
    email_read_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extension_contacts_owner_added
    ON extension_contacts (owner_ip, added_at DESC);

CREATE INDEX IF NOT EXISTS idx_extension_contacts_email
    ON extension_contacts (email);

CREATE UNIQUE INDEX IF NOT EXISTS idx_extension_contacts_primary_email_unique
    ON extension_contacts (LOWER(email))
    WHERE email <> '';

COMMENT ON TABLE extension_contacts IS
    'Chrome extension My List — one row per GitHub login; emails claimed per operator IP';
