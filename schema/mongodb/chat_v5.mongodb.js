/**
 * MongoDB equivalent of schema/chat_v5.sql
 * Chat v5 — chat_direct_pairs collection.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v5.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v5.mongodb.js to " + mongoDbName());

// chat_direct_pairs
idx("chat_direct_pairs", { keys: {"user_a": 1, "user_b": 1}, "unique": true,"name": "chat_direct_pairs_unique" });

print("Done.");
