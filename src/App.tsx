import React, { useState } from 'react';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ConversationalChat } from './components/ConversationalChat';

// --- Types ---
export type DayOfWeek = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI';

export interface MeetingTime {
  day: DayOfWeek;
  startTime: string;
  endTime: string;
}

export interface CourseSection {
  id: string;
  courseCode: string;
  title: string;
  meetings: MeetingTime[];
}

export interface EvaluationResult {
  riskScore: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  conflicts: string[];
}

// --- Mock Data & Constants ---
const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
const START_HOUR = 8;
const END_HOUR = 18;
const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60;

const MOCK_SECTIONS: CourseSection[] = [
  {
    id: 'sec-1',
    courseCode: 'CS 101',
    title: 'Intro to Computer Science',
    meetings: [
      { day: 'MON', startTime: '09:00', endTime: '10:30' },
      { day: 'WED', startTime: '09:00', endTime: '10:30' },
    ],
  },
  {
    id: 'sec-2',
    courseCode: 'MATH 201',
    title: 'Calculus I',
    meetings: [
      { day: 'MON', startTime: '10:00', endTime: '11:30' },
      { day: 'WED', startTime: '10:00', endTime: '11:30' },
    ],
  },
];

// --- Helpers ---
function parseTimeToMinutes(timeStr: string): number {
  const [hours, minutes] = timeStr.split(':').map(Number);
  return hours * 60 + minutes;
}

function getConflictingSectionIds(sections: CourseSection[]): Set<string> {
  const conflictingIds = new Set<string>();
  for (let i = 0; i < sections.length; i++) {
    for (let j = i + 1; j < sections.length; j++) {
      const secA = sections[i];
      const secB = sections[j];
      for (const mA of secA.meetings) {
        for (const mB of secB.meetings) {
          if (mA.day === mB.day && mA.startTime < mB.endTime && mB.startTime < mA.endTime) {
            conflictingIds.add(secA.id);
            conflictingIds.add(secB.id);
          }
        }
      }
    }
  }
  return conflictingIds;
}

function calculateBlockStyle(startTime: string, endTime: string) {
  const startMins = parseTimeToMinutes(startTime) - START_HOUR * 60;
  const durationMins = parseTimeToMinutes(endTime) - parseTimeToMinutes(startTime);
  return {
    top: `${(startMins / TOTAL_MINUTES) * 100}%`,
    height: `${(durationMins / TOTAL_MINUTES) * 100}%`,
  };
}

export default function App() {
  const [currentView, setCurrentView] = useState<'welcome' | 'forms' | 'chat'>('welcome');

  const [major, setMajor] = useState('');
  const [modality, setModality] = useState('HYBRID');
  const [semester, setSemester] = useState('Fall 2026'); // State for the active semester
  
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evaluationResults, setEvaluationResults] = useState<EvaluationResult | null>(null);

  const conflictingIds = getConflictingSectionIds(MOCK_SECTIONS);
  const hours = Array.from({ length: 11 }, (_, i) => i + 8);

  const handleRunEvaluation = async () => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const response = await fetch('http://localhost:8000/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ major, modality, semester }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}: ${response.statusText}`);
      }

      const data: EvaluationResult = await response.json();
      setEvaluationResults(data);
    } catch (err: any) {
      setEvaluationResults({
        riskScore: 65,
        riskLevel: 'MEDIUM',
        conflicts: ['CS 101 and MATH 201 overlap on Mon/Wed from 10:00 to 10:30.'],
      });
      setEvalError(err.message ? `Backend offline (using fallback mock data): ${err.message}` : null);
    } finally {
      setEvalLoading(false);
    }
  };

  if (currentView === 'welcome') {
    return <WelcomeScreen onNavigate={(view) => setCurrentView(view)} />;
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', display: 'flex', flexDirection: 'column', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      
      {/* Modern Glass Navbar */}
      <header style={{ backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', padding: '1rem 2.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: '0 1px 3px 0 rgba(0,0,0,0.05)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }} onClick={() => setCurrentView('welcome')}>
          <div style={{ width: '36px', height: '36px', backgroundColor: '#2563eb', borderRadius: '10px', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '15px', boxShadow: '0 4px 6px -1px rgba(37,99,235,0.3)' }}>
            SA
          </div>
          <div>
            <span style={{ fontWeight: '800', color: '#0f172a', fontSize: '1.1rem', display: 'block', lineHeight: '1.2' }}>SmartAdvisor</span>
            <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: '500' }}>Academic Intelligence Suite</span>
          </div>
        </div>
        <nav style={{ display: 'flex', gap: '0.5rem', background: '#f1f5f9', padding: '0.25rem', borderRadius: '10px' }}>
          <button
            onClick={() => setCurrentView('welcome')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem', color: '#64748b', padding: '0.5rem 1rem', borderRadius: '8px', transition: 'all 0.2s' }}
          >
            Home
          </button>
          <button
            onClick={() => setCurrentView('forms')}
            style={{ background: currentView === 'forms' ? '#ffffff' : 'none', color: currentView === 'forms' ? '#2563eb' : '#64748b', boxShadow: currentView === 'forms' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', border: 'none', padding: '0.5rem 1rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem' }}
          >
            Forms & Engines
          </button>
          <button
            onClick={() => setCurrentView('chat')}
            style={{ background: currentView === 'chat' ? '#ffffff' : 'none', color: currentView === 'chat' ? '#2563eb' : '#64748b', boxShadow: currentView === 'chat' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', border: 'none', padding: '0.5rem 1rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem' }}
          >
            AI Assistant Chat
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '2.5rem', maxWidth: '1400px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
        
        {currentView === 'forms' && (
          <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '2rem', alignItems: 'start' }}>
            
            {/* Left Column: Preferences & Risk Evaluation Card */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ padding: '1.75rem', backgroundColor: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.02)' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#0f172a', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>⚙️</span> Student Preferences
                </h2>
                
                <div style={{ display: 'grid', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '700', color: '#475569', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.025em' }}>
                      Major / Program
                    </label>
                    <input
                      type="text"
                      value={major}
                      onChange={(e) => setMajor(e.target.value)}
                      placeholder="e.g., Computer Science"
                      style={{ width: '100%', padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '0.9rem', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '700', color: '#475569', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.025em' }}>
                      Modality Preference
                    </label>
                    <select
                      value={modality}
                      onChange={(e) => setModality(e.target.value)}
                      style={{ width: '100%', padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '10px', fontSize: '0.9rem', boxSizing: 'border-box', outline: 'none', backgroundColor: '#fff' }}
                    >
                      <option value="IN_PERSON">In Person</option>
                      <option value="ONLINE">Online</option>
                      <option value="HYBRID">Hybrid</option>
                    </select>
                  </div>
                  <button
                    onClick={handleRunEvaluation}
                    disabled={evalLoading}
                    style={{
                      padding: '0.85rem',
                      backgroundColor: '#2563eb',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '10px',
                      fontWeight: '700',
                      fontSize: '0.9rem',
                      cursor: 'pointer',
                      marginTop: '0.5rem',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)',
                      transition: 'background 0.2s'
                    }}
                  >
                    {evalLoading ? 'Evaluating Engine...' : 'Run Risk & Conflict Check'}
                  </button>
                </div>

                {evalLoading && (
                  <div style={{ marginTop: '1rem', color: '#2563eb', fontSize: '0.85rem', fontWeight: '500', textAlign: 'center' }}>
                    Analyzing schedule rules...
                  </div>
                )}

                {evalError && (
                  <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', borderRadius: '8px', fontSize: '0.8rem' }}>
                    {evalError}
                  </div>
                )}

                {evaluationResults && !evalLoading && (
                  <div style={{ marginTop: '1.5rem', padding: '1.25rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
                    <h3 style={{ fontWeight: '700', marginBottom: '0.75rem', fontSize: '0.95rem', color: '#0f172a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Evaluation Output</span>
                      <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', background: '#fef2f2', color: '#dc2626', borderRadius: '20px', fontWeight: '700' }}>
                        {evaluationResults.riskLevel} Risk
                      </span>
                    </h3>
                    <p style={{ fontSize: '0.85rem', marginBottom: '0.75rem', color: '#334155' }}>
                      <strong>Risk Score:</strong> <span style={{ color: '#2563eb', fontWeight: '700' }}>{evaluationResults.riskScore} / 100</span>
                    </p>
                    <div style={{ fontSize: '0.8rem' }}>
                      <strong style={{ color: '#475569', display: 'block', marginBottom: '0.25rem' }}>Conflict Highlights:</strong>
                      <ul style={{ margin: '0', paddingLeft: '1.2rem', color: '#dc2626', lineHeight: '1.4' }}>
                        {evaluationResults.conflicts.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Schedule Display Card */}
            <div style={{ padding: '1.75rem', backgroundColor: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                  📅 Course Schedule Display
                </h2>
                
                {/* Interactive Semester Selector */}
                <select
                  value={semester}
                  onChange={(e) => setSemester(e.target.value)}
                  style={{
                    fontSize: '0.75rem',
                    color: '#334155',
                    background: '#f1f5f9',
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    fontWeight: '600',
                    border: '1px solid #cbd5e1',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="Fall 2026">Fall Semester 2026</option>
                  <option value="Spring 2027">Spring Semester 2027</option>
                  <option value="Summer 2027">Summer Term 2027</option>
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '70px repeat(5, 1fr)', border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                <div style={{ padding: '0.75rem 0.5rem', fontWeight: '700', fontSize: '0.75rem', color: '#64748b', borderRight: '1px solid #e2e8f0', backgroundColor: '#f8fafc', textAlign: 'center' }}>
                  Time
                </div>
                {DAYS.map((d) => (
                  <div key={d} style={{ padding: '0.75rem 0.5rem', fontWeight: '700', fontSize: '0.8rem', color: '#0f172a', textAlign: 'center', borderRight: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
                    {d}
                  </div>
                ))}

                <div style={{ borderRight: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
                  {hours.map((h) => (
                    <div key={h} style={{ height: '52px', borderBottom: '1px solid #e2e8f0', fontSize: '0.7rem', color: '#64748b', padding: '4px', textAlign: 'right', paddingRight: '8px' }}>
                      {h}:00
                    </div>
                  ))}
                </div>

                {DAYS.map((day) => (
                  <div key={day} style={{ position: 'relative', borderRight: '1px solid #e2e8f0', height: '572px', backgroundColor: '#ffffff' }}>
                    {hours.map((h) => (
                      <div key={h} style={{ height: '52px', borderBottom: '1px solid #f1f5f9' }} />
                    ))}

                    {MOCK_SECTIONS.flatMap((sec) =>
                      sec.meetings
                        .filter((m) => m.day === day)
                        .map((m, idx) => {
                          const isConflict = conflictingIds.has(sec.id);
                          const stylePos = calculateBlockStyle(m.startTime, m.endTime);

                          return (
                            <div
                              key={`${sec.id}-${idx}`}
                              style={{
                                position: 'absolute',
                                width: '90%',
                                left: '5%',
                                ...stylePos,
                                padding: '8px',
                                borderRadius: '8px',
                                fontSize: '0.75rem',
                                border: isConflict ? '1px solid #fca5a5' : '1px solid #93c5fd',
                                backgroundColor: isConflict ? '#fef2f2' : '#eff6ff',
                                color: isConflict ? '#991b1b' : '#1e40af',
                                boxSizing: 'border-box',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                              }}
                            >
                              <strong style={{ display: 'block', fontSize: '0.8rem' }}>{sec.courseCode}</strong>
                              <div style={{ fontSize: '0.7rem', opacity: 0.9 }}>{sec.title}</div>
                              {isConflict && (
                                <span style={{ display: 'inline-block', marginTop: '4px', backgroundColor: '#dc2626', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: '700' }}>
                                  ⚠️ Overlap
                                </span>
                              )}
                            </div>
                          );
                        })
                    )}
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {currentView === 'chat' && (
          <div style={{ maxWidth: '900px', margin: '0 auto', height: '78vh', backgroundColor: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.05)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ConversationalChat />
          </div>
        )}

      </main>
    </div>
  );
}