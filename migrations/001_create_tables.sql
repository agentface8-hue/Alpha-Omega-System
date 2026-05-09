-- Alpha-Omega Signal Storage — Supabase DDL
-- Run this once in the Supabase SQL editor (Dashboard → SQL Editor → New query)
-- Tables "signals" and "signal_reports" already exist; this adds missing tables.

-- ── signals (already exists — shown for reference) ──────────────────────────
-- CREATE TABLE IF NOT EXISTS signals (
--   id          TEXT PRIMARY KEY,
--   ticker      TEXT,
--   status      TEXT DEFAULT 'active',
--   asset_type  TEXT DEFAULT 'stock',
--   data        JSONB,
--   created_at  TIMESTAMPTZ DEFAULT now(),
--   updated_at  TIMESTAMPTZ DEFAULT now(),
--   closed_at   TIMESTAMPTZ
-- );

-- ── signal_reports (already exists — shown for reference) ────────────────────
-- CREATE TABLE IF NOT EXISTS signal_reports (
--   id          TEXT PRIMARY KEY,
--   signal_id   TEXT,
--   ticker      TEXT,
--   data        JSONB,
--   created_at  TIMESTAMPTZ DEFAULT now()
-- );

-- ── action_log (NEW — create this) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS action_log (
  id          BIGSERIAL PRIMARY KEY,
  signal_id   TEXT,
  ticker      TEXT,
  entry       JSONB,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_action_log_signal_id ON action_log (signal_id);
CREATE INDEX IF NOT EXISTS idx_action_log_ticker    ON action_log (ticker);
CREATE INDEX IF NOT EXISTS idx_action_log_created   ON action_log (created_at DESC);

-- ── case_reports (alias table — same structure as signal_reports) ─────────────
-- Not strictly needed since signal_reports already serves this role.
-- CREATE TABLE IF NOT EXISTS case_reports (
--   id          TEXT PRIMARY KEY,
--   signal_id   TEXT,
--   symbol      TEXT,
--   data        JSONB,
--   created_at  TIMESTAMPTZ DEFAULT now()
-- );

-- ── Enable RLS (allow anon key to read/write) ────────────────────────────────
ALTER TABLE action_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Allow all on action_log"
  ON action_log FOR ALL
  USING (true)
  WITH CHECK (true);
