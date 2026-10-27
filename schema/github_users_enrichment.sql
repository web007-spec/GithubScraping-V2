-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/github_users_enrichment.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor (required for full profile data)
-- Safe to run multiple times (IF NOT EXISTS)

ALTER TABLE github_users ADD COLUMN IF NOT EXISTS blog TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS twitter_username TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS github_url TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS public_gists INTEGER;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS email_source TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS all_emails JSONB DEFAULT '[]'::jsonb;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS social_links JSONB DEFAULT '[]'::jsonb;
ALTER TABLE github_users ADD COLUMN IF NOT EXISTS profile_data JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN github_users.description IS 'Combined profile text: bio, company, links';
COMMENT ON COLUMN github_users.profile_data IS 'Full GitHub API payload (profile, emails, social)';
COMMENT ON COLUMN github_users.all_emails IS 'All public emails from GitHub';
COMMENT ON COLUMN github_users.social_links IS 'Linked social accounts from GitHub';

CREATE INDEX IF NOT EXISTS idx_github_users_email ON github_users (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_github_users_bio ON github_users (bio) WHERE bio IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_github_users_description ON github_users (description) WHERE description IS NOT NULL;
