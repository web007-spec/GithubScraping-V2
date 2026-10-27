-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/github_users_country_indexes.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_github_users_email_scraped
    ON github_users (last_scraped_at DESC, login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_email_followers
    ON github_users (followers DESC, login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_email_created
    ON github_users (created_at DESC, login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_email_login
    ON github_users (login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_email_repos
    ON github_users (public_repos DESC, login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_country_email_scraped
    ON github_users (country, last_scraped_at DESC)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_country_email_followers
    ON github_users (country, followers DESC)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_country_email_created
    ON github_users (country, created_at DESC)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_country_email_login
    ON github_users (country, login)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_country_email_repos
    ON github_users (country, public_repos DESC)
    WHERE email IS NOT NULL;

-- Partial index per scrape country (optimizes WHERE country = 'X' from other PCs)
CREATE INDEX IF NOT EXISTS idx_gu_country_us ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'US' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_india ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'India' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_uk ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'UK' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_germany ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Germany' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_canada ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Canada' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_japan ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Japan' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_france ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'France' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_brazil ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Brazil' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_australia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Australia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_netherlands ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Netherlands' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_sweden ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Sweden' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_spain ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Spain' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_italy ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Italy' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_poland ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Poland' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_ukraine ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Ukraine' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_russia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Russia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_china ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'China' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_indonesia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Indonesia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_nigeria ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Nigeria' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_israel ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Israel' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_mexico ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Mexico' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_argentina ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Argentina' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_philippines ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Philippines' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_vietnam ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Vietnam' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_turkey ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Turkey' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_czech_republic ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Czech Republic' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_portugal ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Portugal' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_romania ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Romania' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_pakistan ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Pakistan' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_singapore ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Singapore' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_switzerland ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Switzerland' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_norway ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Norway' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_denmark ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Denmark' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_finland ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Finland' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_belgium ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Belgium' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_austria ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Austria' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_ireland ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Ireland' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_united_arab_emirates ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'United Arab Emirates' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_saudi_arabia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Saudi Arabia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_qatar ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Qatar' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_chile ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Chile' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_colombia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Colombia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_peru ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Peru' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_thailand ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Thailand' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_malaysia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Malaysia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_bangladesh ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Bangladesh' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_sri_lanka ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Sri Lanka' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_nepal ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Nepal' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_south_africa ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'South Africa' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_egypt ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Egypt' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_kenya ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Kenya' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_morocco ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Morocco' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_greece ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Greece' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_hungary ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Hungary' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_bulgaria ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Bulgaria' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_serbia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Serbia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_croatia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Croatia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_slovakia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Slovakia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_slovenia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Slovenia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_lithuania ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Lithuania' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_estonia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Estonia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_latvia ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Latvia' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_new_zealand ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'New Zealand' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_taiwan ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Taiwan' AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gu_country_hong_kong ON github_users (last_scraped_at DESC, followers DESC, login) WHERE country = 'Hong Kong' AND email IS NOT NULL;

-- Catch-all for any other country value stored in the future
CREATE INDEX IF NOT EXISTS idx_github_users_country_other
    ON github_users (country, last_scraped_at DESC)
    WHERE email IS NOT NULL AND country IS NOT NULL;

-- Fast admin search for "%term%" filters in /users.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_github_users_login_trgm
    ON github_users USING gin (login gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_github_users_name_trgm
    ON github_users USING gin (name gin_trgm_ops)
    WHERE name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_email_trgm
    ON github_users USING gin (email gin_trgm_ops)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_company_trgm
    ON github_users USING gin (company gin_trgm_ops)
    WHERE company IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_location_trgm
    ON github_users USING gin (location gin_trgm_ops)
    WHERE location IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_github_users_bio_trgm
    ON github_users USING gin (bio gin_trgm_ops)
    WHERE bio IS NOT NULL;

ANALYZE github_users;
