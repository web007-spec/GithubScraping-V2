/**
 * MongoDB equivalent of schema/chat_v7.sql
 * Chat v7 — client message dedupe index on chat_messages.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v7.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v7.mongodb.js to " + mongoDbName());

// chat_messages
idx("chat_messages", { keys: {"id": 1}, "unique": true,"name": "chat_messages_id_unique" });
idx("chat_messages", { keys: {"conversation_id": 1, "created_at": -1}, "name": "chat_messages_conv_created" });
idx("chat_messages", { keys: {"client_message_id": 1}, "sparse": true,"name": "chat_messages_client_message_id" });
idx("chat_messages", { keys: {"conversation_id": 1, "sender_id": 1, "client_message_id": 1}, "unique": true,"name": "chat_messages_client_dedupe","partialFilterExpression": {"client_message_id": {"$exists": true,"$type": "string","$gt": "" });

print("Done.");
