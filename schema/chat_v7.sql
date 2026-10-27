-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v7.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after schema/chat_v6.sql.

CREATE TABLE IF NOT EXISTS chat_reactions (
  message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  emoji TEXT NOT NULL CHECK (char_length(emoji) BETWEEN 1 AND 16),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_reactions_message
  ON chat_reactions(message_id);

ALTER TABLE chat_reactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Members read reactions" ON chat_reactions;
CREATE POLICY "Members read reactions"
ON chat_reactions FOR SELECT TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM chat_messages msg
    JOIN chat_members mem ON mem.conversation_id = msg.conversation_id
    WHERE msg.id = chat_reactions.message_id
      AND mem.user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS "Users insert own reactions" ON chat_reactions;
CREATE POLICY "Users insert own reactions"
ON chat_reactions FOR INSERT TO authenticated
WITH CHECK (
  user_id = auth.uid()
  AND EXISTS (
    SELECT 1
    FROM chat_messages msg
    JOIN chat_members mem ON mem.conversation_id = msg.conversation_id
    WHERE msg.id = chat_reactions.message_id
      AND msg.deleted_at IS NULL
      AND msg.message_type <> 'system'
      AND mem.user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS "Users update own reactions" ON chat_reactions;
CREATE POLICY "Users update own reactions"
ON chat_reactions FOR UPDATE TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users delete own reactions" ON chat_reactions;
CREATE POLICY "Users delete own reactions"
ON chat_reactions FOR DELETE TO authenticated
USING (user_id = auth.uid());

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_reactions;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
