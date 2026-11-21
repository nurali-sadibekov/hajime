  -- Run once in the Supabase SQL editor (Dashboard -> SQL Editor).
  -- One row per user holds all of that user's boards, tasks and study history.

  create table if not exists public.user_data (
    user_id    uuid primary key references auth.users (id) on delete cascade,
    data       jsonb not null,
    updated_by text,
    updated_at timestamptz not null default now()
  );

  -- Abuse guard: one user cannot store an unbounded document (the app stays far below this).
alter table public.user_data drop constraint if exists user_data_limits;
alter table public.user_data add constraint user_data_limits
  check (pg_column_size(data) <= 2000000 and char_length(coalesce(updated_by, '')) <= 64);

create or replace function public.touch_user_data() returns trigger
  language plpgsql as $$
  begin
    new.updated_at = now();
    return new;
  end $$;

  drop trigger if exists user_data_touch on public.user_data;
  create trigger user_data_touch before update on public.user_data
    for each row execute function public.touch_user_data();

  -- Each user can only see and change their own row.
  alter table public.user_data enable row level security;

  drop policy if exists "own row: select" on public.user_data;
  drop policy if exists "own row: insert" on public.user_data;
  drop policy if exists "own row: update" on public.user_data;
  drop policy if exists "own row: delete" on public.user_data;
  create policy "own row: select" on public.user_data for select
    using ((select auth.uid()) = user_id);
  create policy "own row: insert" on public.user_data for insert
    with check ((select auth.uid()) = user_id);
  create policy "own row: update" on public.user_data for update
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
  create policy "own row: delete" on public.user_data for delete
    using ((select auth.uid()) = user_id);

  -- Real-time sync between devices.
  do $$ begin
    alter publication supabase_realtime add table public.user_data;
  exception when duplicate_object then null; end $$;
