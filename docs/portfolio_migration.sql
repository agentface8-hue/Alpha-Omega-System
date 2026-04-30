-- Alpha-Omega: Portfolio Tab Migration
-- Run this once in Supabase SQL Editor: https://supabase.com/dashboard/project/nchkslvakbcykpiizotn/sql

-- 1. Positions table (open + closed)
CREATE TABLE IF NOT EXISTS portfolio_positions (
  id          TEXT PRIMARY KEY,
  ticker      TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'open',  -- open, partial, closed
  asset_type  TEXT DEFAULT 'stock',
  data        JSONB NOT NULL,
  updated_at  TIMESTAMPTZ DEFAULT now(),
  closed_at   TIMESTAMPTZ
);

-- 2. Portfolio state (single row — cash, totals)
CREATE TABLE IF NOT EXISTS portfolio_state (
  id            TEXT PRIMARY KEY DEFAULT 'main',
  data          JSONB NOT NULL DEFAULT '{}',
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Seed the initial state row
INSERT INTO portfolio_state (id, data)
VALUES ('main', '{
  "cash": 25000,
  "total_value": 25000,
  "starting_capital": 25000,
  "max_positions": 5,
  "max_position_size": 10000,
  "min_position_size": 5000,
  "max_risk_per_trade": 500,
  "split_tp1_pct": 50,
  "split_tp2_pct": 30,
  "split_tp3_pct": 20,
  "trailing_enabled": true
}')
ON CONFLICT (id) DO NOTHING;

-- Optional: enable RLS + anon access
ALTER TABLE portfolio_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_positions" ON portfolio_positions FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_state"     ON portfolio_state     FOR ALL TO anon USING (true) WITH CHECK (true);
