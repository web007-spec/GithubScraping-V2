# MongoDB schema (replaces `schema/*.sql` when using MongoDB)

When `DATABASE_STORAGE=mongodb`, **do not run the `.sql` files**. They are Postgres/Supabase only.

## Apply schema

**Recommended (Python — works without mongosh):**

```powershell
cd "E:\my work\extension\githubScraiping"
python scripts/apply_mongodb_schema.py
```

Rebuild country stats (replaces SQL trigger in `country_stats.sql`):

```powershell
python scripts/apply_mongodb_schema.py --rebuild-country-stats
```

**VS Code MongoDB extension** (`.mongodb.js` files in the sidebar):

1. Install the [MongoDB for VS Code](https://marketplace.visualstudio.com/items?itemName=mongodb.mongodb-vscode) extension.
2. Connect to `mongodb://127.0.0.1:27017` (same as `MONGODB_URI` in `.env`).
3. Open a file such as `schema/mongodb/google_docs_archive.mongodb.js`.
4. Click **Run** (play button) at the top of the file, or use **MongoDB: Run All From Playground**.

Run from the **project root** so `load("schema/mongodb/_common.mongodb.js")` resolves correctly.

**Alternative (mongosh CLI — if installed):**

```powershell
mongosh "mongodb://127.0.0.1:27017/outreach_console" schema/mongodb/setup.mongodb.js
```

## SQL file mapping

| Postgres SQL | MongoDB collection(s) | Notes |
|--------------|----------------------|--------|
| `management_tables.sql` | `scraping_runs`, `github_tokens`, `scheduled_jobs` | RLS → app auth |
| `github_users.sql` | `github_users` | |
| `github_users_country_indexes.sql` | partial indexes on `github_users` | In `setup.mongodb.js` |
| `country_stats.sql` | `github_user_country_stats` | Use `--rebuild-country-stats` |
| `google_documents.sql`, `google_docs_*.sql` | `google_documents`, `google_docs_crawl_runs` | |
| `chat.sql`, `chat_v*.sql` | `chat_*` collections | File storage → local `chat-files/` |
| `extension_*.sql` | `extension_*`, `registration_ip_locks` | |
| `app_releases.sql` | `app_releases` | |
| `profile_avatars_storage.sql` | N/A | Supabase Storage only |
| `extension_anon_read.sql` | N/A | Postgres RLS policies |

## Source of truth

- Indexes: `backend/outreach_db/mongodb_schema.py`
- Full setup: `schema/mongodb/setup.mongodb.js` (auto-generated)
- Per-module scripts: `schema/mongodb/*.mongodb.js` (auto-generated from SQL filenames)

Regenerate after changing `mongodb_schema.py`:

```powershell
python scripts/generate_mongodb_setup_js.py
python scripts/generate_mongodb_module_scripts.py
```
