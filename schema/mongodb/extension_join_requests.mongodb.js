/**
 * MongoDB equivalent of schema/extension_join_requests.sql
 * Collection `extension_join_requests`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/extension_join_requests.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/extension_join_requests.mongodb.js to " + mongoDbName());

// extension_join_requests
idx("extension_join_requests", { keys: {"id": 1}, "unique": true,"name": "extension_join_requests_id_unique" });
idx("extension_join_requests", { keys: {"owner_ip": 1}, "unique": true,"name": "extension_join_requests_owner_ip_unique" });
idx("extension_join_requests", { keys: {"status": 1, "requested_at": -1}, "name": "extension_join_requests_status" });

print("Done.");
