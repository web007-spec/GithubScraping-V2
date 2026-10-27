/**
 * MongoDB equivalent of schema/extension_ai_access_requests.sql
 * Collection `extension_ai_access_requests`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/extension_ai_access_requests.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/extension_ai_access_requests.mongodb.js to " + mongoDbName());

// extension_ai_access_requests
idx("extension_ai_access_requests", { keys: {"id": 1}, "unique": true,"name": "extension_ai_access_id_unique" });

print("Done.");
