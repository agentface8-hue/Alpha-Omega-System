-- Migration 004: Calibration Params — Supabase persistence
-- Replaces Render ephemeral calibration/calibration_params.json
-- Run once in Supabase SQL Editor: Dashboard → SQL Editor → New query

-- ── calibration_params (singleton row keyed on 'default') ────────────────────
CREATE TABLE IF NOT EXISTS calibration_params (
    key         TEXT PRIMARY KEY DEFAULT 'default',
    params      JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed with empty row so upsert always hits an existing record
INSERT INTO calibration_params (key, params)
VALUES ('default', '{"mode":"none","scale":1.0,"offset":0}')
ON CONFLICT (key) DO NOTHING;

-- RLS: allow the anon key to read and write this table
ALTER TABLE calibration_params ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Allow all on calibration_params"
    ON calibration_params FOR ALL
    USING (true)
    WITH CHECK (true);
