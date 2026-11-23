import { supabase } from '../lib/supabase';
import { conversationTitle, MAX_SAVED_CONVERSATIONS, MAX_SAVED_MESSAGE_CHARACTERS, MAX_SAVED_MESSAGES } from '../utils/conversationHistory';

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  expires_at: string;
}

export interface SavedConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  display_metadata: Record<string, unknown>;
  created_at: string;
}

export async function createConversation(userId: string, firstMessage: string): Promise<string> {
  const { data, error } = await supabase
    .from('chat_conversations')
    .insert({ user_id: userId, title: conversationTitle(firstMessage) })
    .select('id')
    .single();
  if (error) throw error;
  return String(data.id);
}

export async function saveConversationMessage(
  userId: string,
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  displayMetadata: Record<string, unknown>,
): Promise<void> {
  const { error } = await supabase.from('chat_messages').insert({
    user_id: userId,
    conversation_id: conversationId,
    role,
    content: content.slice(0, MAX_SAVED_MESSAGE_CHARACTERS),
    display_metadata: displayMetadata,
  });
  if (error) throw error;
}

export async function listConversationHistory(userId: string): Promise<ConversationSummary[]> {
  const { data, error } = await supabase
    .from('chat_conversations')
    .select('id, title, created_at, updated_at, expires_at')
    .eq('user_id', userId)
    .gt('expires_at', new Date().toISOString())
    .order('updated_at', { ascending: false })
    .limit(MAX_SAVED_CONVERSATIONS);
  if (error) throw error;
  return (data ?? []) as ConversationSummary[];
}

export async function loadConversationMessages(userId: string, conversationId: string): Promise<SavedConversationMessage[]> {
  const { data, error } = await supabase
    .from('chat_messages')
    .select('id, role, content, display_metadata, created_at')
    .eq('user_id', userId)
    .eq('conversation_id', conversationId)
    .order('created_at', { ascending: true })
    .limit(MAX_SAVED_MESSAGES);
  if (error) throw error;
  return (data ?? []) as SavedConversationMessage[];
}

export async function deleteConversation(userId: string, conversationId: string): Promise<void> {
  const { error } = await supabase.from('chat_conversations').delete().eq('user_id', userId).eq('id', conversationId);
  if (error) throw error;
}
