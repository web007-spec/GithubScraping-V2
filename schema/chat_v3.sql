-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v3.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after schema/chat.sql and chat_v2.sql.

CREATE TABLE IF NOT EXISTS chat_presence (
  user_id UUID PRIMARY KEY,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_online BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_chat_typing_conversation_updated
  ON chat_typing(conversation_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_members_conversation
  ON chat_members(conversation_id);

ALTER TABLE chat_presence ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated read presence" ON chat_presence;
CREATE POLICY "Authenticated read presence"
ON chat_presence FOR SELECT TO authenticated
USING (true);

DROP POLICY IF EXISTS "Users upsert own presence" ON chat_presence;
CREATE POLICY "Users upsert own presence"
ON chat_presence FOR INSERT TO authenticated
WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users update own presence" ON chat_presence;
CREATE POLICY "Users update own presence"
ON chat_presence FOR UPDATE TO authenticated
USING (user_id = auth.uid());

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_presence;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
