/**
 * MongoDB equivalent of schema/chat_v3.sql
 * Chat v3 — chat_reactions collection.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v3.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v3.mongodb.js to " + mongoDbName());

// chat_reactions
idx("chat_reactions", { keys: {"message_id": 1, "user_id": 1, "emoji": 1}, "unique": true,"name": "chat_reactions_unique" });

print("Done.");
