-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v2.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after schema/chat.sql.

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE chat_conversations
  ADD COLUMN IF NOT EXISTS created_by UUID;

CREATE INDEX IF NOT EXISTS idx_chat_messages_not_deleted
  ON chat_messages(conversation_id, created_at DESC)
  WHERE deleted_at IS NULL;

-- Realtime updates for edits/deletes
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_members;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
