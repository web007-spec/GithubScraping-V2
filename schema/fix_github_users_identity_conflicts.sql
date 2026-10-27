-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/fix_github_users_identity_conflicts.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor if old scraper runs inserted inconsistent rows.

BEGIN;

-- Keep the newest row for any duplicated login variants if the unique index was
-- ever missing during imports. The normal schema has login UNIQUE, so this is a
-- defensive repair for older databases only.
WITH ranked AS (
  SELECT
    ctid,
    ROW_NUMBER() OVER (
      PARTITION BY lower(login)
      ORDER BY last_scraped_at DESC NULLS LAST, updated_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM github_users
)
DELETE FROM github_users g
USING ranked r
WHERE g.ctid = r.ctid
  AND r.rn > 1;

-- Ensure both stable GitHub id and login stay protected.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'github_users'::regclass
      AND conname = 'github_users_login_key'
  ) THEN
    ALTER TABLE github_users
      ADD CONSTRAINT github_users_login_key UNIQUE (login);
  END IF;
END $$;

COMMIT;
