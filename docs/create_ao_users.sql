-- Alpha-Omega user management table
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS ao_users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username      TEXT UNIQUE NOT NULL,
  display_name  TEXT,
  password_hash TEXT NOT NULL,
  email         TEXT,
  role          TEXT DEFAULT 'visitor' CHECK (role IN ('owner', 'visitor')),
  login_count   INTEGER DEFAULT 0,
  last_login    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast username lookup
CREATE INDEX IF NOT EXISTS idx_ao_users_username ON ao_users(username);
