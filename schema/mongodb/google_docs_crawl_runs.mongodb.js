/**
 * MongoDB equivalent of schema/google_docs_crawl_runs.sql
 * Collection `google_docs_crawl_runs`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/google_docs_crawl_runs.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/google_docs_crawl_runs.mongodb.js to " + mongoDbName());

// google_docs_crawl_runs
idx("google_docs_crawl_runs", { keys: {"id": 1}, "unique": true,"name": "google_docs_crawl_runs_id_unique" });
idx("google_docs_crawl_runs", { keys: {"status": 1, "created_at": -1}, "name": "google_docs_crawl_runs_status_created" });

print("Done.");
