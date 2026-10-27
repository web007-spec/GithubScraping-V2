/**
 * MongoDB equivalent of schema/auth_users
 * Collection `auth_users` for MongoDB auth mode (no Postgres SQL file).
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/auth_users.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/auth_users.mongodb.js to " + mongoDbName());

// auth_users
idx("auth_users", { keys: {"id": 1}, "unique": true,"name": "auth_users_id_unique" });
idx("auth_users", { keys: {"email": 1}, "unique": true,"name": "auth_users_email_unique" });

print("Done.");
