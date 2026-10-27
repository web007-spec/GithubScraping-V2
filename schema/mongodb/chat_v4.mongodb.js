/**
 * MongoDB equivalent of schema/chat_v4.sql
 * Chat v4 — chat_presence collection.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v4.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v4.mongodb.js to " + mongoDbName());

// chat_presence
idx("chat_presence", { keys: {"user_id": 1}, "unique": true,"name": "chat_presence_user_unique" });

print("Done.");
