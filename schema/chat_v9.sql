-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v9.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Global text channels + message replies (run after schema/chat_v8.sql)

ALTER TABLE chat_conversations DROP CONSTRAINT IF EXISTS chat_conversations_type_check;
ALTER TABLE chat_conversations ADD CONSTRAINT chat_conversations_type_check
  CHECK (type IN ('direct', 'group', 'channel'));

ALTER TABLE chat_conversations
  ADD COLUMN IF NOT EXISTS slug TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conversations_slug
  ON chat_conversations(slug) WHERE slug IS NOT NULL;

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS reply_to_id UUID REFERENCES chat_messages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_reply_to
  ON chat_messages(reply_to_id) WHERE reply_to_id IS NOT NULL;

INSERT INTO chat_conversations (type, name, slug, created_at, updated_at)
SELECT 'channel', 'general', 'general', now(), now()
WHERE NOT EXISTS (
  SELECT 1 FROM chat_conversations WHERE slug = 'general'
);
