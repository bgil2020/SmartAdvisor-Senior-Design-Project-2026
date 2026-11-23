-- Repair Data API privileges for chat-history tables created by the earlier migration.
-- RLS remains authoritative: authenticated users can reach only their own rows.

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

grant usage on schema public to authenticated;
revoke all on table public.chat_conversations from anon, authenticated;
revoke all on table public.chat_messages from anon, authenticated;
grant select, insert, delete on table public.chat_conversations to authenticated;
grant select, insert on table public.chat_messages to authenticated;

drop policy if exists "Users manage their own conversations" on public.chat_conversations;
drop policy if exists "Users read their own conversations" on public.chat_conversations;
drop policy if exists "Users create their own conversations" on public.chat_conversations;
drop policy if exists "Users delete their own conversations" on public.chat_conversations;
create policy "Users read their own conversations"
  on public.chat_conversations for select to authenticated
  using (auth.uid() = user_id);
create policy "Users create their own conversations"
  on public.chat_conversations for insert to authenticated
  with check (auth.uid() = user_id);
create policy "Users delete their own conversations"
  on public.chat_conversations for delete to authenticated
  using (auth.uid() = user_id);

drop policy if exists "Users manage their own conversation messages" on public.chat_messages;
drop policy if exists "Users read their own conversation messages" on public.chat_messages;
drop policy if exists "Users create their own conversation messages" on public.chat_messages;
create policy "Users read their own conversation messages"
  on public.chat_messages for select to authenticated
  using (auth.uid() = user_id);
create policy "Users create their own conversation messages"
  on public.chat_messages for insert to authenticated
  with check (auth.uid() = user_id);

notify pgrst, 'reload schema';
