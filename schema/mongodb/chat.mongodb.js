/**
 * MongoDB equivalent of schema/chat.sql
 * Chat collections: chat_conversations, chat_members, chat_messages, chat_typing, chat_direct_pairs, chat_presence, chat_reactions.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat.mongodb.js to " + mongoDbName());

// chat_conversations
idx("chat_conversations", { keys: {"id": 1}, "unique": true,"name": "chat_conversations_id_unique" });
idx("chat_conversations", { keys: {"last_message_at": -1}, "name": "chat_conversations_last_message" });

// chat_members
idx("chat_members", { keys: {"conversation_id": 1, "user_id": 1}, "unique": true,"name": "chat_members_conv_user_unique" });
idx("chat_members", { keys: {"user_id": 1}, "name": "chat_members_user" });

// chat_messages
idx("chat_messages", { keys: {"id": 1}, "unique": true,"name": "chat_messages_id_unique" });
idx("chat_messages", { keys: {"conversation_id": 1, "created_at": -1}, "name": "chat_messages_conv_created" });
idx("chat_messages", { keys: {"client_message_id": 1}, "sparse": true,"name": "chat_messages_client_message_id" });
idx("chat_messages", { keys: {"conversation_id": 1, "sender_id": 1, "client_message_id": 1}, "unique": true,"name": "chat_messages_client_dedupe","partialFilterExpression": {"client_message_id": {"$exists": true,"$type": "string","$gt": "" });

// chat_typing
idx("chat_typing", { keys: {"conversation_id": 1, "user_id": 1}, "unique": true,"name": "chat_typing_conv_user_unique" });

// chat_direct_pairs
idx("chat_direct_pairs", { keys: {"user_a": 1, "user_b": 1}, "unique": true,"name": "chat_direct_pairs_unique" });

// chat_presence
idx("chat_presence", { keys: {"user_id": 1}, "unique": true,"name": "chat_presence_user_unique" });

// chat_reactions
idx("chat_reactions", { keys: {"message_id": 1, "user_id": 1, "emoji": 1}, "unique": true,"name": "chat_reactions_unique" });

print("Done.");
