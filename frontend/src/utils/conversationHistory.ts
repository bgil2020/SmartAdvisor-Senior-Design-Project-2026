import type { ConversationResponse } from '../services/api';
import type { ConversationSectionContext } from './planningSelection';

export const CHAT_RETENTION_DAYS = 30;
export const MAX_SAVED_CONVERSATIONS = 10;
export const MAX_SAVED_MESSAGES = 50;
export const MAX_SAVED_MESSAGE_CHARACTERS = 4000;

export function conversationTitle(message: string): string {
  const compact = message.replace(/\s+/g, ' ').trim();
  return compact.length > 72 ? `${compact.slice(0, 69)}…` : compact || 'SmartAdvisor conversation';
}

export function safeHistoryMetadata(
  response: ConversationResponse | null,
  selection: ConversationSectionContext[],
): Record<string, unknown> {
  const citations = (response?.citations ?? []).slice(0, 6).map((citation) => ({
    title: String(citation.title ?? 'Official source').slice(0, 240),
    url: typeof citation.url === 'string' && /^https:\/\//i.test(citation.url) ? citation.url.slice(0, 1000) : null,
    locator: String(citation.locator ?? 'source text').slice(0, 240),
    course_code: citation.course_code ? String(citation.course_code).slice(0, 24) : null,
  }));
  return {
    response_status: response?.status ?? null,
    response_label: response?.status === 'grounded_answer' ? 'Source-grounded answer' : response?.status.replaceAll('_', ' ') ?? null,
    citations,
    selection: selection.slice(0, 12).map((section) => ({
      course: section.course,
      section: section.section,
      crn: section.crn,
      term: section.term,
    })),
  };
}
