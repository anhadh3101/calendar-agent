This file contains the database schema for the database I am hosting on Supabase

create table public.agent_profiles (
  -- Identity
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users(id) on delete cascade not null unique,
  display_name    text not null,
  email           text not null unique,

  -- A2A Connection
  agent_url       text,
  agent_id        text unique,

  -- Heartbeat & Liveness
  last_seen_at    timestamptz,
  status          text default 'unregistered'
    check (status in ('online', 'offline', 'unregistered')),

  -- Integration Status
  google_calendar_connected   boolean default false,
  google_calendar_token       text,

  -- Metadata
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);