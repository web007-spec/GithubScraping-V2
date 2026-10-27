-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v6.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after schema/chat_v5.sql.

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS client_message_id TEXT;

ALTER TABLE chat_messages
  ALTER COLUMN client_message_id TYPE TEXT USING client_message_id::text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_client_message_id
  ON chat_messages(conversation_id, sender_id, client_message_id)
  WHERE client_message_id IS NOT NULL;
