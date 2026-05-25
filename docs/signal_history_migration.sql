-- signal_history: enriched historical trades for learning loop
-- Stores all 74+ historical trades with reconstructed pillar/TAS/vol data
-- Run once in Supabase SQL editor

create table if not exists signal_history (
  id              serial primary key,
  created_at      timestamptz default now(),
  ticker          text not null,
  date_closed     text,
  entry_price     numeric,
  exit_price      numeric,
  pnl_pct         numeric,
  conviction      numeric,
  exit_reason     text,
  regime          text,
  asset_type      text default 'stock',
  mae_pct         numeric,
  mfe_pct         numeric,
  tas_num         integer,
  vol_ratio       numeric,
  vol_direction   text,
  tf_daily        text,
  tf_weekly       text,
  tf_65m          text,
  tf_240m         text,
  source          text default 'trade_log',
  notes           text
);

create index if not exists signal_history_date_idx    on signal_history(date_closed);
create index if not exists signal_history_regime_idx  on signal_history(regime);
create index if not exists signal_history_pnl_idx     on signal_history(pnl_pct);
