-- Run this in Supabase SQL editor to create the login_events table
CREATE TABLE IF NOT EXISTS login_events (
  id           BIGSERIAL PRIMARY KEY,
  username     TEXT,
  ip           TEXT,
  location     TEXT,
  country      TEXT,
  country_code TEXT,
  browser      TEXT,
  screen       TEXT,
  timezone     TEXT,
  language     TEXT,
  visitor_id   TEXT,
  visit_count  INTEGER,
  logged_at    TIMESTAMPTZ DEFAULT NOW()
);
