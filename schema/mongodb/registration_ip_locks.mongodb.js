/**
 * MongoDB equivalent of schema/registration_ip_locks.sql
 * Collection `registration_ip_locks`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/registration_ip_locks.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/registration_ip_locks.mongodb.js to " + mongoDbName());

// registration_ip_locks
idx("registration_ip_locks", { keys: {"id": 1}, "unique": true,"name": "registration_ip_locks_id_unique" });
idx("registration_ip_locks", { keys: {"owner_ip": 1}, "unique": true,"name": "registration_ip_locks_owner_ip_unique" });
idx("registration_ip_locks", { keys: {"created_at": -1}, "name": "registration_ip_locks_created" });

print("Done.");
