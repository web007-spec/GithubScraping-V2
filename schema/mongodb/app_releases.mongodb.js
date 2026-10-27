/**
 * MongoDB equivalent of schema/app_releases.sql
 * Collection `app_releases`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/app_releases.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/app_releases.mongodb.js to " + mongoDbName());

// app_releases
idx("app_releases", { keys: {"id": 1}, "unique": true,"name": "app_releases_id_unique" });
idx("app_releases", { keys: {"storage_path": 1}, "unique": true,"name": "app_releases_storage_path_unique" });
idx("app_releases", { keys: {"created_at": -1}, "name": "app_releases_created_at" });
idx("app_releases", { keys: {"is_example": 1}, "unique": true,"name": "app_releases_single_example","partialFilterExpression": {"is_example": true });

print("Done.");
