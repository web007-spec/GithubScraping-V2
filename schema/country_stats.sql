-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/country_stats.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

CREATE TABLE IF NOT EXISTS github_user_country_stats (
    country TEXT PRIMARY KEY,
    user_count BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE github_user_country_stats IS
  'Live row counts per country (users with email). Updated by trigger on github_users.';

CREATE INDEX IF NOT EXISTS idx_country_stats_count
    ON github_user_country_stats (user_count DESC);

-- Rebuild counts from github_users (run once after deploy or backfill)
CREATE OR REPLACE FUNCTION rebuild_github_user_country_stats()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    TRUNCATE github_user_country_stats;
    INSERT INTO github_user_country_stats (country, user_count, updated_at)
    SELECT country, COUNT(*)::bigint, NOW()
    FROM github_users
    WHERE country IS NOT NULL AND email IS NOT NULL
    GROUP BY country;
END;
$$;

-- Fast country list for API (uses stats table)
CREATE OR REPLACE FUNCTION list_github_user_countries()
RETURNS TABLE(country text, user_count bigint)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT country, user_count
    FROM github_user_country_stats
    WHERE user_count > 0
    ORDER BY user_count DESC, country ASC;
$$;

CREATE OR REPLACE FUNCTION trg_github_users_country_stats()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    old_ok BOOLEAN;
    new_ok BOOLEAN;
BEGIN
    old_ok := (TG_OP <> 'INSERT')
        AND (OLD.country IS NOT NULL)
        AND (OLD.email IS NOT NULL);

    new_ok := (TG_OP <> 'DELETE')
        AND (NEW.country IS NOT NULL)
        AND (NEW.email IS NOT NULL);

    IF TG_OP = 'INSERT' AND new_ok THEN
        INSERT INTO github_user_country_stats (country, user_count, updated_at)
        VALUES (NEW.country, 1, NOW())
        ON CONFLICT (country) DO UPDATE
            SET user_count = github_user_country_stats.user_count + 1,
                updated_at = NOW();

    ELSIF TG_OP = 'DELETE' AND old_ok THEN
        UPDATE github_user_country_stats
        SET user_count = GREATEST(0, user_count - 1),
            updated_at = NOW()
        WHERE country = OLD.country;

    ELSIF TG_OP = 'UPDATE' THEN
        IF old_ok AND (NOT new_ok OR OLD.country IS DISTINCT FROM NEW.country) THEN
            UPDATE github_user_country_stats
            SET user_count = GREATEST(0, user_count - 1),
                updated_at = NOW()
            WHERE country = OLD.country;
        END IF;

        IF new_ok AND (NOT old_ok OR OLD.country IS DISTINCT FROM NEW.country) THEN
            INSERT INTO github_user_country_stats (country, user_count, updated_at)
            VALUES (NEW.country, 1, NOW())
            ON CONFLICT (country) DO UPDATE
                SET user_count = github_user_country_stats.user_count + 1,
                    updated_at = NOW();
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS github_users_country_stats_trigger ON github_users;

CREATE TRIGGER github_users_country_stats_trigger
    AFTER INSERT OR UPDATE OF country, email OR DELETE ON github_users
    FOR EACH ROW
    EXECUTE PROCEDURE trg_github_users_country_stats();

-- Backfill stats for existing rows
SELECT rebuild_github_user_country_stats();
