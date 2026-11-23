import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, getRuntimeConfig, sendConversationMessage, type ConversationRequest, type ConversationResponse, type RawSectionRecord } from '../services/api';
import { createConversation, deleteConversation, listConversationHistory, loadConversationMessages, saveConversationMessage, type ConversationSummary, type SavedConversationMessage } from '../services/conversationHistory';
import { commonSelectedTerm, describeSelectedSections, formatTerm, normalizeTermInput, singleSelectedSourceContext, toConversationSections, type ConversationSectionContext } from '../utils/planningSelection';
import { appendTranscriptEntry, isCurrentConversationEpoch } from '../utils/conversationState';
import { historyFailureMessage, safeHistoryMetadata } from '../utils/conversationHistory';
import { DEFAULT_CONVERSATION_REQUEST_TIMEOUT_MS, missingContextLabel, normalizeConversationRequestTimeoutMs, pendingMessagesForRequest, quickPromptsForSelection, responseDetailLabel, type InformationSourcesByCourse } from '../utils/conversationPresentation';
import { mergeSessionEvidence, type SessionEvidenceRecord, type SessionSourceContext } from '../utils/sessionEvidence';

interface SyntheticProfile { student_id: string; name: string; major: string; work_hours: number; recent_difficulty: number; satisfied: 'yes' | 'mostly' | 'no'; recent_courses: string }
const SAMPLE_PROFILES: SyntheticProfile[] = [
  { student_id: 'Z24567901', name: 'Evie Woods', major: 'Electrical Engineering', work_hours: 5, recent_difficulty: 1, satisfied: 'yes', recent_courses: 'CDA4240C, CDA4102, MAC2313' },
  { student_id: 'Z24567891', name: 'Alan Turing', major: 'Computer Science', work_hours: 20, recent_difficulty: 3, satisfied: 'mostly', recent_courses: 'COP3530, COT4400' },
  { student_id: 'Z24567894', name: 'Grace Hopper', major: 'Computer Science', work_hours: 0, recent_difficulty: 2, satisfied: 'yes', recent_courses: 'CDA3201C, COP3530' },
];
interface TranscriptEntry { id: number; role: 'user' | 'assistant'; text: string; response?: ConversationResponse; selectionSnapshot?: ConversationSectionContext[]; failed?: boolean }
interface Props {
  defaultProfileId?: string; defaultWorkHours?: number; defaultDifficulty?: number;
  defaultSatisfaction?: 'yes' | 'mostly' | 'no'; defaultRecentCourses?: string;
  selectedSections?: RawSectionRecord[]; informationSourcesByCourse?: InformationSourcesByCourse; onOverrideHandoff?: (courseCode?: string) => void; accountId?: string | null;
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
      <div className="assistant-response-meta"><span className={`response-status response-${response.status}`}>{responseStatusLabel(response)}</span><span>{responseDetailLabel(response)}</span></div>
      <p>{response.response_text}</p>
      {response.generation_source === 'provider' && <div className="response-generation">Generated from the cited course information.</div>}
      {usedSelectedSchedule && <div className="response-context"><strong>Selected schedule sent:</strong> {describeSelectedSections(selection)}</div>}
      {!usedSelectedSchedule && response.extracted_courses.length > 0 && <div className="response-context"><strong>Courses identified in the question:</strong> {response.extracted_courses.join(', ')}</div>}
      {response.citations && response.citations.length > 0 && (
        <ol aria-label="Source citations" className="response-citations">{response.citations.map((citation, index) => {
          const url = safeSourceUrl(citation.url);
          return <li key={`${String(citation.record_id)}-${index}`}>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{String(citation.title ?? 'Official source')}</a> : String(citation.title ?? 'Official source')}{' — '}{String(citation.locator ?? 'source text')}</li>;
        })}</ol>
      )}
      {response.actionable_guidance && <div className="response-guidance"><strong>Guidance:</strong> {response.actionable_guidance}</div>}
      {response.generation_fallback_used && <div className="response-fallback">A generated summary was unavailable, so the relevant validated source excerpts are shown directly.</div>}
      {response.missing_context.length > 0 && <div className="response-missing"><strong>Missing information:</strong> {response.missing_context.map(missingContextLabel).join(', ')}</div>}
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
  defaultSatisfaction = 'yes', defaultRecentCourses = 'CDA4240C, CDA4102, MAC2313', selectedSections = [], informationSourcesByCourse, onOverrideHandoff, accountId = null,
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
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [pendingStage, setPendingStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [requestTimeoutMs, setRequestTimeoutMs] = useState(DEFAULT_CONVERSATION_REQUEST_TIMEOUT_MS);
  const [viewedConversation, setViewedConversation] = useState<ConversationSummary | null>(null);
  const [viewedMessages, setViewedMessages] = useState<SavedConversationMessage[]>([]);
  const [historyHeight, setHistoryHeight] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('smartadvisor_history_box_height');
      const parsed = Number(saved);
      if (!Number.isNaN(parsed) && parsed >= 160 && parsed <= 900) return parsed;
    }
    return 360;
  });
  const [historyExpanded, setHistoryExpanded] = useState<boolean>(false);
  const [isResizingHistory, setIsResizingHistory] = useState<boolean>(false);
  const historyPanelRef = useRef<HTMLElement | null>(null);
  const sessionEpoch = useRef(0);
  const entryId = useRef(0);
  const pendingRequest = useRef<AbortController | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const userReadOlderMessages = useRef(false);
  const currentSelection = useMemo(() => toConversationSections(selectedSections), [selectedSections]);
  const quickPrompts = useMemo(() => quickPromptsForSelection(currentSelection, informationSourcesByCourse), [currentSelection, informationSourcesByCourse]);
  const pendingMessages = useMemo(() => pendingMessagesForRequest(pendingQuestion, currentSelection.length), [pendingQuestion, currentSelection.length]);

  useEffect(() => {
    const el = historyPanelRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const borderBox = entry.borderBoxSize?.[0];
        const newH = borderBox ? borderBox.blockSize : entry.contentRect.height;
        if (newH >= 160 && !historyExpanded) {
          setHistoryHeight((prev) => (Math.abs(prev - newH) > 4 ? newH : prev));
          try { localStorage.setItem('smartadvisor_history_box_height', String(Math.round(newH))); } catch {}
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [historyOpen, historyExpanded]);

  const handleHistoryResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = historyPanelRef.current?.offsetHeight ?? historyHeight;
    setIsResizingHistory(true);
    document.body.classList.add('resizing-active');

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const workspaceEl = transcriptRef.current?.closest('.conversation-workspace') as HTMLElement | null;
      const maxH = workspaceEl ? Math.max(200, workspaceEl.clientHeight - 200) : 750;
      const nextH = Math.max(160, Math.min(maxH, startH + deltaY));
      setHistoryHeight(nextH);
      try {
        localStorage.setItem('smartadvisor_history_box_height', String(Math.round(nextH)));
      } catch {}
    };

    const handleMouseUp = () => {
      setIsResizingHistory(false);
      document.body.classList.remove('resizing-active');
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleHistoryResizeTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length !== 1) return;
    const startY = e.touches[0].clientY;
    const startH = historyPanelRef.current?.offsetHeight ?? historyHeight;
    setIsResizingHistory(true);

    const handleTouchMove = (moveEvent: TouchEvent) => {
      if (moveEvent.touches.length !== 1) return;
      const deltaY = moveEvent.touches[0].clientY - startY;
      const workspaceEl = transcriptRef.current?.closest('.conversation-workspace') as HTMLElement | null;
      const maxH = workspaceEl ? Math.max(200, workspaceEl.clientHeight - 200) : 750;
      const nextH = Math.max(160, Math.min(maxH, startH + deltaY));
      setHistoryHeight(nextH);
      try {
        localStorage.setItem('smartadvisor_history_box_height', String(Math.round(nextH)));
      } catch {}
    };

    const handleTouchEnd = () => {
      setIsResizingHistory(false);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
    };

    window.addEventListener('touchmove', handleTouchMove);
    window.addEventListener('touchend', handleTouchEnd);
  };

  const handleHistoryResizeKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHistoryHeight((curr) => {
        const next = Math.max(160, curr - 25);
        try { localStorage.setItem('smartadvisor_history_box_height', String(next)); } catch {}
        return next;
      });
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHistoryHeight((curr) => {
        const workspaceEl = transcriptRef.current?.closest('.conversation-workspace') as HTMLElement | null;
        const maxH = workspaceEl ? Math.max(200, workspaceEl.clientHeight - 200) : 750;
        const next = Math.min(maxH, curr + 25);
        try { localStorage.setItem('smartadvisor_history_box_height', String(next)); } catch {}
        return next;
      });
    }
  };

  useEffect(() => { const container = transcriptRef.current; if (container && !userReadOlderMessages.current) container.scrollTop = container.scrollHeight; }, [transcript]);
  useEffect(() => {
    let active = true;
    void getRuntimeConfig()
      .then((config) => { if (active) setRequestTimeoutMs(normalizeConversationRequestTimeoutMs(config.conversation_request_timeout_ms)); })
      .catch(() => { /* Preserve the safe local default when runtime config is unavailable. */ });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => setPendingStage((current) => Math.min(current + 1, pendingMessages.length - 1)), 2200);
    return () => window.clearInterval(timer);
  }, [loading, pendingMessages.length]);

  const handleProfileChange = (profileId: string) => {
    setStudentId(profileId);
    const profile = SAMPLE_PROFILES.find((item) => item.student_id === profileId);
    if (profile) { setWorkHours(profile.work_hours); setRecentDifficulty(profile.recent_difficulty); setSatisfaction(profile.satisfied); setRecentCoursesInput(profile.recent_courses); }
  };

  const refreshHistory = async () => {
    if (!accountId) return;
    setHistoryLoading(true); setHistoryError(null);
    try { setHistory(await listConversationHistory(accountId)); }
    catch (caught) { setHistoryError(historyFailureMessage(caught, 'read')); }
    finally { setHistoryLoading(false); }
  };

  const toggleHistory = () => {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next) void refreshHistory();
  };

  const viewHistoryConversation = async (conversation: ConversationSummary) => {
    if (!accountId) return;
    setHistoryLoading(true); setHistoryError(null);
    try { setViewedMessages(await loadConversationMessages(accountId, conversation.id)); setViewedConversation(conversation); }
    catch (caught) { setHistoryError(historyFailureMessage(caught, 'read')); }
    finally { setHistoryLoading(false); }
  };

  const removeHistoryConversation = async (conversationId: string) => {
    if (!accountId) return;
    try {
      await deleteConversation(accountId, conversationId);
      if (viewedConversation?.id === conversationId) { setViewedConversation(null); setViewedMessages([]); }
      await refreshHistory();
    } catch (caught) { setHistoryError(historyFailureMessage(caught, 'delete')); }
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
    setMessage(''); setPendingQuestion(trimmed); setPendingStage(0); setLoading(true); setError(null);
    const recentCourses = recentCoursesInput.split(',').map((course) => course.trim()).filter(Boolean);
    const selectedTerm = commonSelectedTerm(selectionSnapshot);
    const manualTerm = normalizeTermInput(sourceTerm);
    const selectedSourceContext = singleSelectedSourceContext(selectionSnapshot);
    const payload: ConversationRequest = {
      message: trimmed, student_id: includeContext ? studentId : null, recent_difficulty: includeContext ? Number(recentDifficulty) : null,
      satisfied_with_performance: includeContext ? satisfaction : null, work_hours: includeContext ? Number(workHours) : null,
      preferred_max_credits: 15, recent_courses: includeContext && recentCourses.length > 0 ? recentCourses : null,
      term: (sourceContext?.term_id ?? manualTerm) || selectedTerm,
      sections: selectionSnapshot.length > 0 ? selectionSnapshot : undefined,
      selected_sections: selectionSnapshot.length > 0 ? selectionSnapshot : undefined,
      session_evidence: sessionEvidence,
      session_context: sourceContext ?? (manualTerm || sourceSection.trim() ? { course_code: '', term_id: manualTerm ? String(manualTerm) : null, section: sourceSection.trim() || null } : selectedSourceContext),
    };
    let persistedConversationId = currentConversationId;
    if (accountId) {
      setHistoryError(null);
      try {
        if (!persistedConversationId) {
          persistedConversationId = await createConversation(accountId, trimmed);
          setCurrentConversationId(persistedConversationId);
        }
        await saveConversationMessage(accountId, persistedConversationId, 'user', trimmed, safeHistoryMetadata(null, selectionSnapshot));
      } catch (caught) {
        setHistoryError(historyFailureMessage(caught, 'write'));
      }
    }
    try {
      const timeout = window.setTimeout(() => controller.abort('timeout'), requestTimeoutMs);
      const response = await sendConversationMessage(payload, controller.signal).finally(() => window.clearTimeout(timeout));
      if (!isCurrentConversationEpoch(requestEpoch, sessionEpoch.current)) return;
      if (response.acquired_evidence?.length) setSessionEvidence((current) => mergeSessionEvidence(current, response.acquired_evidence ?? []));
      if (response.source_scope?.course_code) setSourceContext(response.source_scope);
      if (response.target_handler === 'online_override_eligibility_engine') onOverrideHandoff?.(response.extracted_courses[0]);
      setTranscript((current) => appendTranscriptEntry(current, { id: ++entryId.current, role: 'assistant', text: response.response_text, response, selectionSnapshot }));
      if (accountId && persistedConversationId) {
        void saveConversationMessage(accountId, persistedConversationId, 'assistant', response.response_text, safeHistoryMetadata(response, selectionSnapshot))
          .catch((caught) => setHistoryError(historyFailureMessage(caught, 'write')));
      }
    } catch (caught) {
      if (!isCurrentConversationEpoch(requestEpoch, sessionEpoch.current) || (controller.signal.aborted && controller.signal.reason !== 'timeout')) return;
      const detail = controller.signal.reason === 'timeout' ? 'The request timed out before the service completed.' : caught instanceof ApiError ? caught.message : 'Failed to communicate with the conversational service.';
      setError(detail);
      setTranscript((current) => appendTranscriptEntry(current, { id: ++entryId.current, role: 'assistant', text: detail, failed: true, selectionSnapshot }));
    } finally { if (isCurrentConversationEpoch(requestEpoch, sessionEpoch.current)) setLoading(false); }
  };

  const clearChat = () => {
    sessionEpoch.current += 1; pendingRequest.current?.abort(); pendingRequest.current = null;
    setTranscript([]); setSessionEvidence([]); setSourceContext(null); setSourceTerm(''); setSourceSection(''); setError(null); setLoading(false); setMessage(''); setCurrentConversationId(null);
  };

  return (
    <section className="conversation-workspace" aria-labelledby="conversational-assistant-title">
      <header className="conversation-header"><div><h2 id="conversational-assistant-title">SmartAdvisor Chat</h2><p>Ask about the selected schedule or a specifically named course.</p></div><div className="conversation-header-actions">{accountId && <button type="button" className="clear-chat-button" onClick={toggleHistory} aria-expanded={historyOpen}>History</button>}<button type="button" className="clear-chat-button" onClick={clearChat} disabled={transcript.length === 0 && sessionEvidence.length === 0 && !loading}>New chat</button></div></header>
      {historyOpen && (
        <>
          <aside
            ref={historyPanelRef}
            className={`conversation-history ${historyExpanded ? 'conversation-history-expanded' : ''}`}
            aria-label="Saved conversations"
            style={{
              height: historyExpanded ? '75%' : `${historyHeight}px`,
              maxHeight: historyExpanded ? '85%' : 'none',
              flex: 'none',
            }}
          >
            <div className="history-heading">
              <div>
                <strong>Recent conversations</strong>
                <span>Saved for up to 30 days · newest 10</span>
              </div>
              <div className="history-heading-actions">
                <button
                  type="button"
                  className="history-size-btn"
                  onClick={() => setHistoryExpanded((curr) => !curr)}
                  title={historyExpanded ? 'Restore default size' : 'Expand history view for reading'}
                  aria-label={historyExpanded ? 'Restore default size' : 'Expand history view'}
                >
                  {historyExpanded ? 'Restore size' : 'Expand'}
                </button>
                <button type="button" onClick={() => setHistoryOpen(false)}>Close</button>
              </div>
            </div>
            {historyError && <div className="conversation-error" role="alert">{historyError}</div>}
            {historyLoading && <p role="status">Loading conversation history…</p>}
            {!viewedConversation && !historyLoading && (
              <div className="history-list">
                {history.length === 0 ? (
                  <p>No saved conversations yet.</p>
                ) : (
                  history.map((conversation) => (
                    <div className="history-row" key={conversation.id}>
                      <button type="button" onClick={() => void viewHistoryConversation(conversation)}>
                        <strong>{conversation.title}</strong>
                        <span>{new Date(conversation.updated_at).toLocaleString()}</span>
                      </button>
                      <button
                        type="button"
                        className="history-delete"
                        aria-label={`Delete ${conversation.title}`}
                        onClick={() => void removeHistoryConversation(conversation.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
            {viewedConversation && (
              <div className="history-detail">
                <div className="history-detail-header">
                  <button type="button" onClick={() => { setViewedConversation(null); setViewedMessages([]); }}>← All conversations</button>
                  <h3>{viewedConversation.title}</h3>
                  <p className="history-readonly-note">Read-only archive. Starting a new message creates a fresh evidence session.</p>
                </div>
                <div className="history-messages-scroll">
                  {viewedMessages.map((saved) => {
                    const citations = Array.isArray(saved.display_metadata.citations)
                      ? saved.display_metadata.citations as Array<Record<string, unknown>>
                      : [];
                    return (
                      <article className={`history-message history-message-${saved.role}`} key={saved.id}>
                        <small>{saved.role === 'user' ? 'You' : 'SmartAdvisor'}</small>
                        <p>{saved.content}</p>
                        {citations.length > 0 && (
                          <ol>
                            {citations.map((citation, index) => (
                              <li key={index}>
                                {typeof citation.url === 'string'
                                  ? <a href={citation.url} target="_blank" rel="noopener noreferrer">{String(citation.title ?? 'Official source')}</a>
                                  : String(citation.title ?? 'Official source')} — {String(citation.locator ?? 'source text')}
                              </li>
                            ))}
                          </ol>
                        )}
                      </article>
                    );
                  })}
                </div>
              </div>
            )}
          </aside>
          {!historyExpanded && (
            <div
              className={`history-resize-handle ${isResizingHistory ? 'resizing' : ''}`}
              role="separator"
              aria-orientation="horizontal"
              aria-label="Drag to adjust history box height"
              aria-valuenow={Math.round(historyHeight)}
              aria-valuemin={160}
              aria-valuemax={800}
              tabIndex={0}
              onMouseDown={handleHistoryResizeStart}
              onTouchStart={handleHistoryResizeTouchStart}
              onKeyDown={handleHistoryResizeKeyDown}
              title="Drag up or down to adjust history box size"
            >
              <span className="resize-handle-grip" />
            </div>
          )}
        </>
      )}
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
        <div className="source-context-row"><label>Source term<input aria-label="Source term" placeholder="Fall 2026" value={sourceContext?.term_id ? formatTerm(sourceContext.term_id) : sourceTerm} onChange={(event) => { setSourceContext(null); setSourceTerm(event.target.value); }} /></label><label>Section<input aria-label="Source section" placeholder="001" value={sourceContext?.section ?? sourceSection} onChange={(event) => { setSourceContext(null); setSourceSection(event.target.value); }} /></label></div>
      </details>
      <div className="selection-context-banner" role="status"><strong>Shared selection:</strong> {describeSelectedSections(currentSelection)}</div>
      <div className="conversation-transcript" ref={transcriptRef} aria-live="polite" onScroll={(event) => { const element = event.currentTarget; userReadOlderMessages.current = element.scrollHeight - element.scrollTop - element.clientHeight > 80; }}>
        {transcript.length === 0 && <div className="conversation-empty"><strong>Start a planning conversation</strong><p>Select two sections, then ask “Do these classes conflict?” The validated scheduling engine will use their exact CRNs.</p></div>}
        {transcript.map((entry, index) => <article className={`chat-message chat-message-${entry.role} ${entry.failed ? 'chat-message-failed' : ''}`} key={entry.id}>
          {entry.role === 'assistant' ? <AssistantResponse entry={entry} isLatest={index === transcript.length - 1} /> : <><p>{entry.text}</p><small>Selection at send time: {describeSelectedSections(entry.selectionSnapshot ?? [])}</small></>}
        </article>)}
        {loading && <div className="chat-pending" role="status" aria-live="polite">
          <div className="pending-progress-track" aria-hidden="true"><span /></div>
          <div className="pending-message"><span className="pending-dots" aria-hidden="true"><i /><i /><i /></span>{pendingMessages[pendingStage]}</div>
        </div>}
      </div>
      {error && <div className="conversation-error" role="alert">{error}</div>}
      <div className="quick-prompts">{quickPrompts.map((prompt) => <button type="button" key={prompt} onClick={() => setMessage(prompt)}>{prompt}</button>)}{currentSelection.length === 1 && quickPrompts.length === 0 && <span className="quick-prompts-note">Source-based suggestions are unavailable for this course in the current deployment. Schedule questions remain available.</span>}</div>
      <form className="chat-composer" ref={formRef} onSubmit={handleSubmit}>
        <textarea id="conversational-message-input" aria-label="Student Question or Planning Query:" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit(); } }} placeholder="Ask about your selected classes…" rows={3} disabled={loading} />
        <button type="submit" id="conversational-submit-button" disabled={loading || !message.trim()}>{loading ? 'Sending…' : 'Send'}</button>
        <small>Enter sends · Shift+Enter adds a new line</small>
      </form>
    </section>
  );
};
