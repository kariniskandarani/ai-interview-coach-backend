-- Run this once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
-- Adds user scoping to interview_sessions now that Supabase Auth is in use.
-- Nullable: "Try Me" (guest) sessions are never saved at all (see api/main.py), so every
-- row that does exist will have a user_id -- nullable just avoids a backfill migration
-- headache on the existing test rows from before auth existed.

alter table interview_sessions
    add column if not exists user_id uuid references auth.users(id);

create index if not exists interview_sessions_user_id_idx on interview_sessions(user_id);
