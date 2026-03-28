-- ─────────────────────────────────────────────────────────────────────────────
-- AI Trading Agent — Supabase Schema
-- Run this in the Supabase SQL Editor to create all required tables.
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable UUID extension
create extension if not exists "pgcrypto";

-- ── trade_history ─────────────────────────────────────────────────────────────
create table if not exists trade_history (
  id              uuid primary key default gen_random_uuid(),
  symbol          text not null,
  side            text not null check (side in ('BUY', 'SELL')),
  direction       text check (direction in ('LONG', 'SHORT', 'EXIT')),
  qty             numeric(18, 6) not null,
  entry_price     numeric(18, 4) not null,
  exit_price      numeric(18, 4),
  pnl             numeric(18, 4),
  order_id        text,
  confidence      numeric(4, 3) not null default 0,
  reasoning       text,
  thought_log_id  uuid,
  trading_mode    text not null default 'PAPER',
  created_at      timestamptz not null default now(),
  closed_at       timestamptz
);

create index if not exists trade_history_symbol_idx on trade_history(symbol);
create index if not exists trade_history_created_at_idx on trade_history(created_at desc);

-- ── thought_logs ──────────────────────────────────────────────────────────────
create table if not exists thought_logs (
  id          uuid primary key default gen_random_uuid(),
  symbol      text not null,
  action      text not null check (action in ('BUY', 'SELL', 'HOLD')),
  confidence  numeric(4, 3) not null default 0,
  thought_log jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists thought_logs_symbol_idx on thought_logs(symbol);
create index if not exists thought_logs_created_at_idx on thought_logs(created_at desc);

-- ── watchlist ─────────────────────────────────────────────────────────────────
create table if not exists watchlist (
  symbol          text primary key,
  sentiment_score numeric(6, 3) not null default 0,
  last_price      numeric(18, 4),
  notes           text,
  is_active       boolean not null default true,
  updated_at      timestamptz not null default now()
);

create index if not exists watchlist_is_active_idx on watchlist(is_active);

-- ── equity_snapshots (for the equity chart) ───────────────────────────────────
create table if not exists equity_snapshots (
  id              uuid primary key default gen_random_uuid(),
  equity          numeric(18, 4) not null,
  portfolio_value numeric(18, 4) not null,
  created_at      timestamptz not null default now()
);

create index if not exists equity_snapshots_created_at_idx on equity_snapshots(created_at asc);

-- ── Row-Level Security (optional — enable if using anon key on frontend) ──────
-- alter table trade_history enable row level security;
-- alter table thought_logs enable row level security;
-- alter table watchlist enable row level security;
-- alter table equity_snapshots enable row level security;
