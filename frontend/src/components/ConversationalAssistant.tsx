import React, { useState } from 'react';
import {
  sendConversationMessage,
  type ConversationResponse,
  type ConversationRequest,
  ApiError,
} from '../services/api';

interface SyntheticProfile {
  student_id: string;
  name: string;
  major: string;
  work_hours: number;
  recent_difficulty: number;
  satisfied: 'yes' | 'mostly' | 'no';
  recent_courses: string;
}

const SAMPLE_PROFILES: SyntheticProfile[] = [
  {
    student_id: 'Z24567901',
    name: 'Evie Woods',
    major: 'Electrical Engineering',
    work_hours: 5.0,
    recent_difficulty: 1,
    satisfied: 'yes',
    recent_courses: 'CDA4240C, CDA4102, MAC2313',
  },
  {
    student_id: 'Z24567891',
    name: 'Alan Turing',
    major: 'Computer Science',
    work_hours: 20.0,
    recent_difficulty: 3,
    satisfied: 'mostly',
    recent_courses: 'COP3530, COT4400',
  },
  {
    student_id: 'Z24567894',
    name: 'Grace Hopper',
    major: 'Computer Science',
    work_hours: 0.0,
    recent_difficulty: 2,
    satisfied: 'yes',
    recent_courses: 'CDA3201C, COP3530',
  },
];

const SAMPLE_PROMPTS = [
  {
    label: 'Course Compatibility',
    text: 'Can I take COP 4331 and MAP 3305 together?',
  },
  {
    label: 'Missing Details',
    text: 'Can I take COP 3330 together with another course?',
  },
  {
    label: 'Scheduling Overlap',
    text: 'Do COP 3530 section 001 and MAC 2312 section 002 overlap?',
  },
  {
    label: 'Advisor Escalation',
    text: 'Can you register me for COP 3530?',
  },
  {
    label: 'Informational (Inactive RAG)',
    text: 'What topics are covered in COP 3530?',
  },
];

interface Props {
  defaultProfileId?: string;
  defaultWorkHours?: number;
  defaultDifficulty?: number;
  defaultSatisfaction?: 'yes' | 'mostly' | 'no';
  defaultRecentCourses?: string;
}

export const ConversationalAssistant: React.FC<Props> = ({
  defaultProfileId = SAMPLE_PROFILES[0].student_id,
  defaultWorkHours = 5.0,
  defaultDifficulty = 1,
  defaultSatisfaction = 'yes',
  defaultRecentCourses = 'CDA4240C, CDA4102, MAC2313',
}) => {
  const [message, setMessage] = useState('');
  const [studentId, setStudentId] = useState(defaultProfileId);
  const [workHours, setWorkHours] = useState(defaultWorkHours);
  const [recentDifficulty, setRecentDifficulty] = useState(defaultDifficulty);
  const [satisfaction, setSatisfaction] = useState<'yes' | 'mostly' | 'no'>(defaultSatisfaction);
  const [recentCoursesInput, setRecentCoursesInput] = useState(defaultRecentCourses);
  const [includeContext, setIncludeContext] = useState(true);

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<ConversationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProfileChange = (sid: string) => {
    setStudentId(sid);
    const p = SAMPLE_PROFILES.find((prof) => prof.student_id === sid);
    if (p) {
      setWorkHours(p.work_hours);
      setRecentDifficulty(p.recent_difficulty);
      setSatisfaction(p.satisfied);
      setRecentCoursesInput(p.recent_courses);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);

    const recentList = recentCoursesInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const payload: ConversationRequest = {
      message: trimmed,
      student_id: includeContext ? studentId : null,
      recent_difficulty: includeContext ? Number(recentDifficulty) : null,
      satisfied_with_performance: includeContext ? satisfaction : null,
      work_hours: includeContext ? Number(workHours) : null,
      preferred_max_credits: 15.0,
      recent_courses: includeContext && recentList.length > 0 ? recentList : null,
    };

    try {
      const res = await sendConversationMessage(payload);
      setResponse(res);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to communicate with conversational service';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      aria-labelledby="conversational-assistant-title"
      style={{
        padding: '1.5rem',
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}
    >
      <header style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h2 id="conversational-assistant-title" style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#111827', margin: 0 }}>
            Conversational Planning Assistant
          </h2>
          <span
            style={{
              padding: '0.2rem 0.5rem',
              backgroundColor: '#e0f2fe',
              color: '#0369a1',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: '600',
            }}
          >
            Rule-Based Decision-Support Prototype
          </span>
        </div>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', margin: '0.25rem 0 0 0' }}>
          Interprets course compatibility, scheduling, and override questions. Connects directly to the Course Compatibility Engine when workload context is provided.
        </p>
      </header>

      {/* Context Toggle and Parameters */}
      <div
        style={{
          padding: '1rem',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          marginBottom: '1.25rem',
          fontSize: '0.8125rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <label style={{ fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              id="conversational-include-context"
              checked={includeContext}
              onChange={(e) => setIncludeContext(e.target.checked)}
            />
            Attach Synthetic Student & Workload Context
          </label>
          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
            {includeContext ? 'Context attached for compatibility handoff' : 'Testing without context (will trigger clarification)'}
          </span>
        </div>

        {includeContext && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
            <div>
              <label htmlFor="conversational-student-select" style={{ display: 'block', fontWeight: '600', marginBottom: '0.25rem' }}>
                Synthetic Profile:
              </label>
              <select
                id="conversational-student-select"
                value={studentId}
                onChange={(e) => handleProfileChange(e.target.value)}
                style={{ width: '100%', padding: '0.375rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
              >
                {SAMPLE_PROFILES.map((p) => (
                  <option key={p.student_id} value={p.student_id}>
                    {p.name} ({p.student_id}) — {p.major}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="conversational-work-hours" style={{ display: 'block', fontWeight: '600', marginBottom: '0.25rem' }}>
                Work Hours/Week:
              </label>
              <input
                id="conversational-work-hours"
                type="number"
                min="0"
                max="80"
                value={workHours}
                onChange={(e) => setWorkHours(Number(e.target.value))}
                style={{ width: '100%', padding: '0.375rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
              />
            </div>

            <div>
              <label htmlFor="conversational-difficulty" style={{ display: 'block', fontWeight: '600', marginBottom: '0.25rem' }}>
                Past Difficulty (1-5):
              </label>
              <input
                id="conversational-difficulty"
                type="number"
                min="1"
                max="5"
                value={recentDifficulty}
                onChange={(e) => setRecentDifficulty(Number(e.target.value))}
                style={{ width: '100%', padding: '0.375rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
              />
            </div>

            <div>
              <label htmlFor="conversational-satisfaction" style={{ display: 'block', fontWeight: '600', marginBottom: '0.25rem' }}>
                Past Satisfaction:
              </label>
              <select
                id="conversational-satisfaction"
                value={satisfaction}
                onChange={(e) => setSatisfaction(e.target.value as 'yes' | 'mostly' | 'no')}
                style={{ width: '100%', padding: '0.375rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
              >
                <option value="yes">Yes</option>
                <option value="mostly">Mostly</option>
                <option value="no">No</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Quick Prompts */}
      <div style={{ marginBottom: '1rem' }}>
        <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600', marginRight: '0.5rem' }}>
          Try sample prompts:
        </span>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
          {SAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              type="button"
              id={`sample-prompt-btn-${i}`}
              onClick={() => setMessage(p.text)}
              style={{
                padding: '0.25rem 0.5rem',
                fontSize: '0.75rem',
                backgroundColor: '#f1f5f9',
                border: '1px solid #cbd5e1',
                borderRadius: '4px',
                cursor: 'pointer',
                color: '#334155',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Input Form */}
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '0.75rem' }}>
        <div>
          <label
            htmlFor="conversational-message-input"
            style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', color: '#374151', marginBottom: '0.25rem' }}
          >
            Student Question or Planning Query:
          </label>
          <textarea
            id="conversational-message-input"
            rows={2}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g. Can I take COP 4331 and MAP 3305 together?"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.625rem',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '0.875rem',
              fontFamily: 'inherit',
              resize: 'vertical',
            }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          {message && (
            <button
              type="button"
              onClick={() => setMessage('')}
              disabled={loading}
              style={{
                padding: '0.5rem 1rem',
                fontSize: '0.875rem',
                color: '#6b7280',
                backgroundColor: '#ffffff',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Clear
            </button>
          )}
          <button
            type="submit"
            id="conversational-submit-button"
            disabled={loading || !message.trim()}
            style={{
              padding: '0.5rem 1.25rem',
              fontSize: '0.875rem',
              fontWeight: '600',
              color: '#ffffff',
              backgroundColor: loading || !message.trim() ? '#93c5fd' : '#2563eb',
              border: 'none',
              borderRadius: '6px',
              cursor: loading || !message.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Evaluating...' : 'Ask Assistant'}
          </button>
        </div>
      </form>

      {/* Error Banner */}
      {error && (
        <div
          role="alert"
          style={{
            marginTop: '1rem',
            padding: '0.75rem',
            backgroundColor: '#fee2e2',
            border: '1px solid #ef4444',
            borderRadius: '6px',
            color: '#991b1b',
            fontSize: '0.875rem',
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Response Display */}
      {response && (
        <div
          id="conversational-response-card"
          style={{
            marginTop: '1.25rem',
            padding: '1rem',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            backgroundColor: '#ffffff',
          }}
        >
          {/* Status Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '0.2rem 0.6rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                backgroundColor:
                  response.status === 'engine_executed'
                    ? '#dcfce7'
                    : response.status === 'escalation'
                    ? '#fef3c7'
                    : response.status === 'clarification'
                    ? '#e0e7ff'
                    : '#f1f5f9',
                color:
                  response.status === 'engine_executed'
                    ? '#166534'
                    : response.status === 'escalation'
                    ? '#92400e'
                    : response.status === 'clarification'
                    ? '#3730a3'
                    : '#475569',
              }}
            >
              {response.status === 'engine_executed'
                ? 'Compatibility Engine Executed'
                : response.status === 'escalation'
                ? 'Advisor Escalation'
                : response.status === 'clarification'
                ? 'Clarification Needed'
                : response.status === 'rag_inactive'
                ? 'Informational Question (RAG Inactive)'
                : response.status === 'engine_unavailable'
                ? 'Directed to Structured Feature'
                : 'Unsupported Scope'}
            </span>

            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
              Routing: {response.disposition} ({response.target_handler})
            </span>
          </div>

          {/* Primary Response Text */}
          <p style={{ fontSize: '0.9375rem', color: '#1e293b', lineHeight: '1.5', margin: '0.5rem 0' }}>
            {response.response_text}
          </p>

          {/* Actionable Guidance */}
          {response.actionable_guidance && (
            <div style={{ margin: '0.5rem 0', fontSize: '0.8125rem', color: '#0369a1', backgroundColor: '#f0f9ff', padding: '0.5rem', borderRadius: '4px', border: '1px solid #bae6fd' }}>
              <strong>Guidance:</strong> {response.actionable_guidance}
            </div>
          )}

          {/* Missing Context Alert */}
          {response.missing_context && response.missing_context.length > 0 && (
            <div style={{ margin: '0.5rem 0', fontSize: '0.8125rem', color: '#b45309', backgroundColor: '#fffbeb', padding: '0.5rem', borderRadius: '4px', border: '1px solid #fde68a' }}>
              <strong>Missing Required Context:</strong> {response.missing_context.join(', ')}
            </div>
          )}

          {/* Engine Result Box */}
          {response.engine_executed && response.engine_result && (
            <div
              style={{
                marginTop: '1rem',
                padding: '0.875rem',
                backgroundColor: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                fontSize: '0.8125rem',
              }}
            >
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', fontWeight: 'bold', color: '#0f172a' }}>
                Compatibility Analysis Result for {String(response.engine_result.student_name ?? studentId)}
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <div><strong>Proposed Credits:</strong> {String(response.engine_result.proposed_credits ?? 'N/A')}</div>
                <div><strong>Assessment:</strong> {String(response.engine_result.assessment ?? 'N/A')}</div>
              </div>

              {Array.isArray(response.engine_result.recommendations) && response.engine_result.recommendations.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <strong>Recommendations:</strong>
                  <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0 }}>
                    {(response.engine_result.recommendations as string[]).map((rec, idx) => (
                      <li key={idx} style={{ marginTop: '0.2rem' }}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {Boolean(response.engine_result.repeat_course_warning) && (
                <div style={{ marginTop: '0.5rem', color: '#b45309', fontWeight: '600' }}>
                  ⚠️ {String(response.engine_result.repeat_course_warning)}
                </div>
              )}
            </div>
          )}

          {/* Prototype Disclaimer */}
          <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic', borderTop: '1px solid #f1f5f9', paddingTop: '0.5rem' }}>
            {response.disclaimer}
          </div>
        </div>
      )}
    </section>
  );
};
