-- Bounded, user-owned conversation history for the SmartAdvisor demo.
-- Signed session evidence and raw source content must never be stored here.

create table if not exists public.chat_conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text not null check (char_length(title) between 1 and 120),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '30 days'),
    unique (id, user_id),
    check (expires_at <= created_at + interval '31 days')
);

create table if not exists public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null check (char_length(content) between 1 and 4000),
    display_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (conversation_id, user_id)
      references public.chat_conversations(id, user_id) on delete cascade,
    check (jsonb_typeof(display_metadata) = 'object'),
    check (display_metadata::text !~* '"(session_evidence|signature|raw_syllabus|raw_source|prompt|api_key)"[[:space:]]*:')
);

create index if not exists chat_conversations_user_updated_idx
  on public.chat_conversations(user_id, updated_at desc);
create index if not exists chat_messages_conversation_created_idx
  on public.chat_messages(conversation_id, created_at asc);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "Users manage their own conversations" on public.chat_conversations;
create policy "Users manage their own conversations"
  on public.chat_conversations for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users manage their own conversation messages" on public.chat_messages;
create policy "Users manage their own conversation messages"
  on public.chat_messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create or replace function public.maintain_chat_history_bounds()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from public.chat_conversations where expires_at <= now();

  delete from public.chat_conversations
    where id in (
      select id from public.chat_conversations
      where user_id = new.user_id
      order by updated_at desc, id desc
      offset 10
    );

  return new;
end;
$$;

drop trigger if exists maintain_chat_history_bounds_trigger on public.chat_conversations;
create trigger maintain_chat_history_bounds_trigger
after insert or update on public.chat_conversations
for each row execute function public.maintain_chat_history_bounds();

create or replace function public.enforce_chat_message_bound()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (select count(*) from public.chat_messages where conversation_id = new.conversation_id) >= 50 then
    raise exception 'Conversation history is limited to 50 messages';
  end if;
  update public.chat_conversations set updated_at = now() where id = new.conversation_id and user_id = new.user_id;
  return new;
end;
$$;

drop trigger if exists enforce_chat_message_bound_trigger on public.chat_messages;
create trigger enforce_chat_message_bound_trigger
before insert on public.chat_messages
for each row execute function public.enforce_chat_message_bound();

revoke all on function public.maintain_chat_history_bounds() from public;
revoke all on function public.enforce_chat_message_bound() from public;
