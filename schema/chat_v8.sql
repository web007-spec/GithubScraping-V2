-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat_v8.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Password-protected chat messages (run after schema/chat_v7.sql)

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS is_protected BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS password_hash TEXT,
  ADD COLUMN IF NOT EXISTS file_storage_path TEXT;

CREATE TABLE IF NOT EXISTS chat_message_unlocks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_message_unlocks_user
  ON chat_message_unlocks(user_id);

ALTER TABLE chat_message_unlocks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Members read own unlocks" ON chat_message_unlocks;
CREATE POLICY "Members read own unlocks"
ON chat_message_unlocks FOR SELECT TO authenticated
USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users insert own unlocks" ON chat_message_unlocks;
CREATE POLICY "Users insert own unlocks"
ON chat_message_unlocks FOR INSERT TO authenticated
WITH CHECK (user_id = auth.uid());
