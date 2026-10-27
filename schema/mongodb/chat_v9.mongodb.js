/**
 * MongoDB equivalent of schema/chat_v9.sql
 * Global channels (slug) + message replies.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/chat_v9.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/chat_v9.mongodb.js to " + mongoDbName());

const mdb = mongoDb();

idx("chat_conversations", {
  keys: { slug: 1 },
  unique: true,
  name: "chat_conversations_slug_unique",
  partialFilterExpression: { slug: { $type: "string" } },
});

idx("chat_messages", {
  keys: { reply_to_id: 1 },
  sparse: true,
  name: "chat_messages_reply_to",
});

const now = new Date();
if (!mdb.chat_conversations.findOne({ slug: "general" })) {
  mdb.chat_conversations.insertOne({
    id: UUID().toString(),
    type: "channel",
    name: "general",
    slug: "general",
    created_at: now,
    updated_at: now,
  });
  print("Seeded #general channel");
} else {
  print("#general channel already exists");
}

print("Done.");
