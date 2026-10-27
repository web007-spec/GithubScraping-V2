-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/extension_anon_read.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in the same Supabase project as githubScraiping.

ALTER TABLE github_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_user_country_stats ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS extension_read_github_users ON github_users;
CREATE POLICY extension_read_github_users ON github_users
  FOR SELECT
  TO anon, authenticated
  USING (true);

DROP POLICY IF EXISTS extension_read_country_stats ON github_user_country_stats;
CREATE POLICY extension_read_country_stats ON github_user_country_stats
  FOR SELECT
  TO anon, authenticated
  USING (true);
