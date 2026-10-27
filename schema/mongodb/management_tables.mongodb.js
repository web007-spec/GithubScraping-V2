/**
 * MongoDB equivalent of schema/management_tables.sql
 * Collections: scraping_runs, github_tokens, scheduled_jobs.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/management_tables.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/management_tables.mongodb.js to " + mongoDbName());

// scraping_runs
idx("scraping_runs", { keys: {"id": 1}, "unique": true,"name": "scraping_runs_id_unique" });
idx("scraping_runs", { keys: {"status": 1, "created_at": -1}, "name": "scraping_runs_status_created" });

// github_tokens
idx("github_tokens", { keys: {"id": 1}, "unique": true,"name": "github_tokens_id_unique" });
idx("github_tokens", { keys: {"is_active": 1}, "name": "github_tokens_active" });

// scheduled_jobs
idx("scheduled_jobs", { keys: {"id": 1}, "unique": true,"name": "scheduled_jobs_id_unique" });
idx("scheduled_jobs", { keys: {"active": 1, "next_run_at": 1}, "name": "scheduled_jobs_active_next" });

print("Done.");
