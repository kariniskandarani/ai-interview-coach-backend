-- Run this once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
-- We use jsonb columns instead of a normalized multi-table schema because a session's
-- transcript is always read/written as one unit, never queried row-by-row -- normalizing
-- it would add join complexity with no practical benefit at this scale.

create table if not exists interview_sessions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    role_type text not null,
    profile jsonb not null,
    transcript jsonb not null,
    report jsonb
);
