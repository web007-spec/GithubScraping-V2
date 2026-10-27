/**
 * MongoDB equivalent of schema/chat_v8.sql
 * Password-protected messages: is_protected fields on chat_messages + chat_message_unlocks.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v8.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v8.mongodb.js to " + mongoDbName());

// chat_messages
idx("chat_messages", { keys: {"id": 1}, "unique": true,"name": "chat_messages_id_unique" });
idx("chat_messages", { keys: {"conversation_id": 1, "created_at": -1}, "name": "chat_messages_conv_created" });
idx("chat_messages", { keys: {"client_message_id": 1}, "sparse": true,"name": "chat_messages_client_message_id" });
idx("chat_messages", { keys: {"conversation_id": 1, "sender_id": 1, "client_message_id": 1}, "unique": true,"name": "chat_messages_client_dedupe","partialFilterExpression": {"client_message_id": {"$exists": true,"$type": "string","$gt": "" });

// chat_message_unlocks
idx("chat_message_unlocks", { keys: {"id": 1}, "unique": true,"name": "chat_message_unlocks_id_unique" });
idx("chat_message_unlocks", { keys: {"message_id": 1, "user_id": 1}, "unique": true,"name": "chat_message_unlocks_msg_user_unique" });
idx("chat_message_unlocks", { keys: {"user_id": 1}, "name": "chat_message_unlocks_user" });

print("Done.");
