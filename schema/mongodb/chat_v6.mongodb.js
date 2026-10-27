/**
 * MongoDB equivalent of schema/chat_v6.sql
 * Chat v6 — chat_typing collection.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v6.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v6.mongodb.js to " + mongoDbName());

// chat_typing
idx("chat_typing", { keys: {"conversation_id": 1, "user_id": 1}, "unique": true,"name": "chat_typing_conv_user_unique" });

print("Done.");
