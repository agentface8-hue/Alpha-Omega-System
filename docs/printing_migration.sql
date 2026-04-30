-- Printing Profits Migration
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/nchkslvakbcykpiizotn/sql

CREATE TABLE IF NOT EXISTS printing_positions (
  id         TEXT PRIMARY KEY,
  ticker     TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'open',
  direction  TEXT NOT NULL DEFAULT 'long',
  data       JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now(),
  closed_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS printing_state (
  id         TEXT PRIMARY KEY DEFAULT 'main',
  data       JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO printing_state (id, data)
VALUES ('main', '{"cash":25000,"total_value":25000,"starting_capital":25000,
"long_exposure":0,"short_exposure":0}')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE printing_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE printing_state     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_printing_positions" ON printing_positions
  FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_printing_state" ON printing_state
  FOR ALL TO anon USING (true) WITH CHECK (true);
