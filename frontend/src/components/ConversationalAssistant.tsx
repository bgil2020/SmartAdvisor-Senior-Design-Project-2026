import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, sendConversationMessage, type ConversationRequest, type ConversationResponse, type RawSectionRecord } from '../services/api';
import { commonSelectedTerm, describeSelectedSections, toConversationSections, type ConversationSectionContext } from '../utils/planningSelection';
import { appendTranscriptEntry, isCurrentConversationEpoch } from '../utils/conversationState';
import { mergeSessionEvidence, type SessionEvidenceRecord, type SessionSourceContext } from '../utils/sessionEvidence';

interface SyntheticProfile { student_id: string; name: string; major: string; work_hours: number; recent_difficulty: number; satisfied: 'yes' | 'mostly' | 'no'; recent_courses: string }
const SAMPLE_PROFILES: SyntheticProfile[] = [
  { student_id: 'Z24567901', name: 'Evie Woods', major: 'Electrical Engineering', work_hours: 5, recent_difficulty: 1, satisfied: 'yes', recent_courses: 'CDA4240C, CDA4102, MAC2313' },
  { student_id: 'Z24567891', name: 'Alan Turing', major: 'Computer Science', work_hours: 20, recent_difficulty: 3, satisfied: 'mostly', recent_courses: 'COP3530, COT4400' },
  { student_id: 'Z24567894', name: 'Grace Hopper', major: 'Computer Science', work_hours: 0, recent_difficulty: 2, satisfied: 'yes', recent_courses: 'CDA3201C, COP3530' },
];
const SAMPLE_PROMPTS = ['Do these classes conflict?', 'Can I take COP 4331 and MAP 3305 together?', 'What topics are covered in COP 4331?'];

interface TranscriptEntry { id: number; role: 'user' | 'assistant'; text: string; response?: ConversationResponse; selectionSnapshot?: ConversationSectionContext[]; failed?: boolean }
interface Props {
  defaultProfileId?: string; defaultWorkHours?: number; defaultDifficulty?: number;
  defaultSatisfaction?: 'yes' | 'mostly' | 'no'; defaultRecentCourses?: string;
  selectedSections?: RawSectionRecord[]; onOverrideHandoff?: (courseCode?: string) => void;
}

function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  try { const parsed = new URL(value); return ['https:', 'http:'].includes(parsed.protocol) ? parsed.href : null; } catch { return null; }
}

function responseStatusLabel(response: ConversationResponse): string {
  const labels: Record<ConversationResponse['status'], string> = {
    engine_executed: 'Backend engine result', clarification: 'Clarification needed', escalation: 'Advisor escalation',
    rag_inactive: 'Informational response', unsupported: 'Unsupported scope', engine_unavailable: 'Structured feature required',
    engine_error: 'Engine error', grounded_answer: 'Source-Grounded Session Answer', acquisition_failed: 'Source Unavailable', no_relevant_evidence: 'Source Unavailable',
  };
  return labels[response.status];
}

function AssistantResponse({ entry, isLatest }: { entry: TranscriptEntry; isLatest: boolean }) {
  const response = entry.response;
  if (!response) return <p>{entry.text}</p>;
  const selection = entry.selectionSnapshot ?? [];
  const usedSelectedSchedule = response.target_handler === 'scheduling_engine' && selection.length > 0;
  return (
    <div id={isLatest ? 'conversational-response-card' : undefined} className="assistant-response-card">
      <div className="assistant-response-meta"><span className={`response-status response-${response.status}`}>{responseStatusLabel(response)}</span><span>{response.target_handler} · {response.response_code}</span></div>
      <p>{response.response_text}</p>
      {usedSelectedSchedule && <div className="response-context"><strong>Selected schedule sent:</strong> {describeSelectedSections(selection)}</div>}
      {!usedSelectedSchedule && response.extracted_courses.length > 0 && <div className="response-context"><strong>Courses identified in the question:</strong> {response.extracted_courses.join(', ')}</div>}
      {response.citations && response.citations.length > 0 && (
        <ol aria-label="Source citations" className="response-citations">{response.citations.map((citation, index) => {
          const url = safeSourceUrl(citation.url);
          return <li key={`${String(citation.record_id)}-${index}`}>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{String(citation.title ?? 'Official source')}</a> : String(citation.title ?? 'Official source')}{' — '}{String(citation.locator ?? 'source text')}</li>;
        })}</ol>
      )}
      {response.actionable_guidance && <div className="response-guidance"><strong>Guidance:</strong> {response.actionable_guidance}</div>}
      {response.generation_fallback_used && <div className="response-fallback"><strong>Cited fallback:</strong> The configured answer provider was unavailable or not enabled, so validated source excerpts are shown.</div>}
      {response.missing_context.length > 0 && <div className="response-missing"><strong>Missing information:</strong> {response.missing_context.join(', ')}</div>}
      {response.engine_executed && response.engine_result && (
        <div className="response-engine-result">
          {response.engine_result.assessment != null && <p><strong>Assessment:</strong> {String(response.engine_result.assessment)}</p>}
          {response.engine_result.conflict_summary != null && <p><strong>Conflict:</strong> {String(response.engine_result.conflict_summary)}</p>}
          {response.engine_result.schedule_status != null && <p><strong>Schedule status:</strong> {String(response.engine_result.schedule_status)}</p>}
          {Array.isArray(response.engine_result.recommendations) && response.engine_result.recommendations.length > 0 && <ul>{response.engine_result.recommendations.map((item, index) => <li key={index}>{String(item)}</li>)}</ul>}
        </div>
      )}
      <small className="response-disclaimer">{response.disclaimer}</small>
    </div>
  );
}

export const ConversationalAssistant: React.FC<Props> = ({
  defaultProfileId = SAMPLE_PROFILES[0].student_id, defaultWorkHours = 5, defaultDifficulty = 1,
  defaultSatisfaction = 'yes', defaultRecentCourses = 'CDA4240C, CDA4102, MAC2313', selectedSections = [], onOverrideHandoff,
}) => {
  const [message, setMessage] = useState('');
  const [studentId, setStudentId] = useState(defaultProfileId);
  const [workHours, setWorkHours] = useState(defaultWorkHours);
  const [recentDifficulty, setRecentDifficulty] = useState(defaultDifficulty);
  const [satisfaction, setSatisfaction] = useState<'yes' | 'mostly' | 'no'>(defaultSatisfaction);
  const [recentCoursesInput, setRecentCoursesInput] = useState(defaultRecentCourses);
  const [includeContext, setIncludeContext] = useState(true);
  const [sessionEvidence, setSessionEvidence] = useState<SessionEvidenceRecord[]>([]);
  const [sourceContext, setSourceContext] = useState<SessionSourceContext | null>(null);
  const [sourceTerm, setSourceTerm] = useState('');
  const [sourceSection, setSourceSection] = useState('');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionEpoch = useRef(0);
  const entryId = useRef(0);
  const pendingRequest = useRef<AbortController | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const userReadOlderMessages = useRef(false);
  const currentSelection = useMemo(() => toConversationSections(selectedSections), [selectedSections]);

  useEffect(() => { const container = transcriptRef.current; if (container && !userReadOlderMessages.current) container.scrollTop = container.scrollHeight; }, [transcript]);

  const handleProfileChange = (profileId: string) => {
    setStudentId(profileId);
    const profile = SAMPLE_PROFILES.find((item) => item.student_id === profileId);
    if (profile) { setWorkHours(profile.work_hours); setRecentDifficulty(profile.recent_difficulty); setSatisfaction(profile.satisfied); setRecentCoursesInput(profile.recent_courses); }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || loading) return;
    const selectionSnapshot = toConversationSections(selectedSections);
    const requestEpoch = sessionEpoch.current;
    const controller = new AbortController();
    pendingRequest.current = controller;
    userReadOlderMessages.current = false;
    setTranscript((current) => appendTranscriptEntry(current, { id: ++entryId.current, role: 'user', text: trimmed, selectionSnapshot }));
    setMessage(''); setLoading(true); setError(null);
    const recentCourses = recentCoursesInput.split(',').map((course) => course.trim()).filter(Boolean);
    const selectedTerm = commonSelectedTerm(selectionSnapshot);
    const payload: ConversationRequest = {
      message: trimmed, student_id: includeContext ? studentId : null, recent_difficulty: includeContext ? Number(recentDifficulty) : null,
      satisfied_with_performance: includeContext ? satisfaction : null, work_hours: includeContext ? Number(workHours) : null,
      preferred_max_credits: 15, recent_courses: includeContext && recentCourses.length > 0 ? recentCourses : null,
      term: (sourceContext?.term_id ?? sourceTerm.trim()) || selectedTerm,
      sections: selectionSnapshot.length > 0 ? selectionSnapshot : undefined,
      selected_sections: selectionSnapshot.length > 0 ? selectionSnapshot : undefined,
      session_evidence: sessionEvidence,
      session_context: sourceContext ?? (sourceTerm.trim() || sourceSection.trim() ? { course_code: '', term_id: sourceTerm.trim() || null, section: sourceSection.trim() || null } : null),
    };
    try {
      const timeout = window.setTimeout(() => controller.abort('timeout'), 45_000);
      const response = await sendConversationMessage(payload, controller.signal).finally(() => window.clearTimeout(timeout));
      if (!isCurrentConversationEpoch(requestEpoch, sessionEpoch.current)) return;
      if (response.acquired_evidence?.length) setSessionEvidence((current) => mergeSessionEvidence(current, response.acquired_evidence ?? []));
      if (response.source_scope?.course_code) setSourceContext(response.source_scope);
      if (response.target_handler === 'online_override_eligibility_engine') onOverrideHandoff?.(response.extracted_courses[0]);
      setTranscript((current) => appendTranscriptEntry(current, { id: ++entryId.current, role: 'assistant', text: response.response_text, response, selectionSnapshot }));
    } catch (caught) {
      if (!isCurrentConversationEpoch(requestEpoch, sessionEpoch.current) || (controller.signal.aborted && controller.signal.reason !== 'timeout')) return;
      const detail = controller.signal.reason === 'timeout' ? 'The request timed out before the service completed.' : caught instanceof ApiError ? caught.message : 'Failed to communicate with the conversational service.';
      setError(detail);
      setTranscript((current) => appendTranscriptEntry(current, { id: ++entryId.current, role: 'assistant', text: detail, failed: true, selectionSnapshot }));
    } finally { if (isCurrentConversationEpoch(requestEpoch, sessionEpoch.current)) setLoading(false); }
  };

  const clearChat = () => {
    sessionEpoch.current += 1; pendingRequest.current?.abort(); pendingRequest.current = null;
    setTranscript([]); setSessionEvidence([]); setSourceContext(null); setSourceTerm(''); setSourceSection(''); setError(null); setLoading(false); setMessage('');
  };

  return (
    <section className="conversation-workspace" aria-labelledby="conversational-assistant-title">
      <header className="conversation-header"><div><h2 id="conversational-assistant-title">SmartAdvisor Chat</h2><p>Ask about the selected schedule or a specifically named course.</p></div><button type="button" className="clear-chat-button" onClick={clearChat} disabled={transcript.length === 0 && sessionEvidence.length === 0 && !loading}>Clear chat</button></header>
      <details className="conversation-context-controls">
        <summary>Conversation context &amp; source evidence</summary>
        <label><input type="checkbox" checked={includeContext} onChange={(event) => setIncludeContext(event.target.checked)} /> Attach synthetic workload context</label>
        {includeContext && <div className="context-grid">
          <label>Profile<select value={studentId} onChange={(event) => handleProfileChange(event.target.value)}>{SAMPLE_PROFILES.map((profile) => <option key={profile.student_id} value={profile.student_id}>{profile.name} — {profile.major}</option>)}</select></label>
          <label>Work hours<input type="number" min="0" max="80" value={workHours} onChange={(event) => setWorkHours(Number(event.target.value))} /></label>
          <label>Past difficulty<input type="number" min="1" max="5" value={recentDifficulty} onChange={(event) => setRecentDifficulty(Number(event.target.value))} /></label>
          <label>Past satisfaction<select value={satisfaction} onChange={(event) => setSatisfaction(event.target.value as 'yes' | 'mostly' | 'no')}><option value="yes">Yes</option><option value="mostly">Mostly</option><option value="no">No</option></select></label>
          <label className="context-wide">Recent courses<input value={recentCoursesInput} onChange={(event) => setRecentCoursesInput(event.target.value)} /></label>
        </div>}
        <div className="source-context-row"><label>Source term<input aria-label="Source term" placeholder="202608" value={sourceContext?.term_id ?? sourceTerm} onChange={(event) => { setSourceContext(null); setSourceTerm(event.target.value); }} /></label><label>Section<input aria-label="Source section" placeholder="002" value={sourceContext?.section ?? sourceSection} onChange={(event) => { setSourceContext(null); setSourceSection(event.target.value); }} /></label></div>
      </details>
      <div className="selection-context-banner" role="status"><strong>Shared selection:</strong> {describeSelectedSections(currentSelection)}</div>
      <div className="conversation-transcript" ref={transcriptRef} aria-live="polite" onScroll={(event) => { const element = event.currentTarget; userReadOlderMessages.current = element.scrollHeight - element.scrollTop - element.clientHeight > 80; }}>
        {transcript.length === 0 && <div className="conversation-empty"><strong>Start a planning conversation</strong><p>Select two sections, then ask “Do these classes conflict?” The validated scheduling engine will use their exact CRNs.</p></div>}
        {transcript.map((entry, index) => <article className={`chat-message chat-message-${entry.role} ${entry.failed ? 'chat-message-failed' : ''}`} key={entry.id}>
          {entry.role === 'assistant' ? <AssistantResponse entry={entry} isLatest={index === transcript.length - 1} /> : <><p>{entry.text}</p><small>Selection at send time: {describeSelectedSections(entry.selectionSnapshot ?? [])}</small></>}
        </article>)}
        {loading && <div className="chat-pending" role="status">SmartAdvisor is checking the integrated backend…</div>}
      </div>
      {error && <div className="conversation-error" role="alert">{error}</div>}
      <div className="quick-prompts">{SAMPLE_PROMPTS.map((prompt) => <button type="button" key={prompt} onClick={() => setMessage(prompt)}>{prompt}</button>)}</div>
      <form className="chat-composer" ref={formRef} onSubmit={handleSubmit}>
        <textarea id="conversational-message-input" aria-label="Student Question or Planning Query:" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit(); } }} placeholder="Ask about your selected classes…" rows={3} disabled={loading} />
        <button type="submit" id="conversational-submit-button" disabled={loading || !message.trim()}>{loading ? 'Sending…' : 'Send'}</button>
        <small>Enter sends · Shift+Enter adds a new line</small>
      </form>
    </section>
  );
};
