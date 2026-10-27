-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/chat.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

-- Run in Supabase SQL Editor after other schema migrations.

CREATE TABLE IF NOT EXISTS chat_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL DEFAULT 'direct' CHECK (type IN ('direct', 'group')),
  name TEXT,
  created_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_message_at TIMESTAMPTZ,
  last_message_preview TEXT
);

CREATE TABLE IF NOT EXISTS chat_members (
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_read_at TIMESTAMPTZ,
  PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_members_user ON chat_members(user_id);

CREATE TABLE IF NOT EXISTS chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL,
  content TEXT,
  client_message_id TEXT,
  message_type TEXT NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'file', 'system')),
  file_url TEXT,
  file_name TEXT,
  file_size BIGINT,
  file_mime TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  edited_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

ALTER TABLE chat_messages
  ALTER COLUMN client_message_id TYPE TEXT USING client_message_id::text;

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
  ON chat_messages(conversation_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_client_message_id
  ON chat_messages(conversation_id, sender_id, client_message_id)
  WHERE client_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS chat_typing (
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (conversation_id, user_id)
);

-- Direct-message uniqueness helper (pair of two users)
CREATE TABLE IF NOT EXISTS chat_direct_pairs (
  user_a UUID NOT NULL,
  user_b UUID NOT NULL,
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  PRIMARY KEY (user_a, user_b),
  CHECK (user_a < user_b)
);

ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_typing ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_direct_pairs ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS; policies for authenticated Realtime reads.
DROP POLICY IF EXISTS "Members read conversations" ON chat_conversations;
CREATE POLICY "Members read conversations"
ON chat_conversations FOR SELECT TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM chat_members m
    WHERE m.conversation_id = id AND m.user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS "Members read membership" ON chat_members;
CREATE POLICY "Members read membership"
ON chat_members FOR SELECT TO authenticated
USING (user_id = auth.uid() OR EXISTS (
  SELECT 1 FROM chat_members m
  WHERE m.conversation_id = chat_members.conversation_id AND m.user_id = auth.uid()
));

DROP POLICY IF EXISTS "Members read messages" ON chat_messages;
CREATE POLICY "Members read messages"
ON chat_messages FOR SELECT TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM chat_members m
    WHERE m.conversation_id = chat_messages.conversation_id AND m.user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS "Members read typing" ON chat_typing;
CREATE POLICY "Members read typing"
ON chat_typing FOR SELECT TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM chat_members m
    WHERE m.conversation_id = chat_typing.conversation_id AND m.user_id = auth.uid()
  )
);

-- Realtime (safe to re-run)
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_messages;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_typing;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_conversations;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE chat_members;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Storage bucket for chat attachments
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'chat-files',
  'chat-files',
  TRUE,
  10485760,
  ARRAY[
    'image/png', 'image/jpeg', 'image/webp', 'image/gif',
    'application/pdf',
    'text/plain',
    'application/zip',
    'application/json'
  ]
)
ON CONFLICT (id) DO UPDATE
SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS "Chat files are publicly readable" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users upload chat files" ON storage.objects;

CREATE POLICY "Chat files are publicly readable"
ON storage.objects FOR SELECT
USING (bucket_id = 'chat-files');

CREATE POLICY "Authenticated users upload chat files"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (
  bucket_id = 'chat-files'
  AND (storage.foldername(name))[1] = auth.uid()::text
);
