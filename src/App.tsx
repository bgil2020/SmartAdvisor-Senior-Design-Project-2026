import { useState, useEffect, useMemo } from 'react';
import OnlineOverrideEvaluator from './components/OnlineOverrideEvaluator';
import { ConversationalAssistant } from './components/ConversationalAssistant';
import {
  getCourses,
  getSections,
  getAlternatives,
  checkCompatibility,
  ApiError,
  type RawCourseRecord,
  type RawSectionRecord,
  type CompatibilityResponse,
} from './services/api';
import {
  DAYS,
  getConflictingSectionIds,
  calculateBlockStyle,
  mapBackendSectionToCourseSection,
  formatMeetingDisplay,
  type CourseSection,
} from './utils/scheduleUtils';
import { MOCK_SECTIONS } from './types/schedule';

// --- Supplied Synthetic Student Profiles (from Synthetic Profiles.xlsx) ---
interface SyntheticProfile {
  student_id: string;
  name: string;
  major: string;
  defaultWorkHours: number;
  recentCourses: string[];
}

const SYNTHETIC_PROFILES: SyntheticProfile[] = [
  {
    student_id: 'Z24567901',
    name: 'Evie Woods',
    major: 'Electrical Engineering',
    defaultWorkHours: 5.0,
    recentCourses: ['CDA4240C', 'CDA4102', 'MAC2313'],
  },
  {
    student_id: 'Z23640867',
    name: 'Emma Smith',
    major: 'Electrical Engineering',
    defaultWorkHours: 10.0,
    recentCourses: ['COP 3014', 'MAC 2311'],
  },
  {
    student_id: 'Z23649212',
    name: 'Amanda Green',
    major: 'Computer Science',
    defaultWorkHours: 15.0,
    recentCourses: ['COP 3530', 'MAD 2104'],
  },
  {
    student_id: 'Z34249087',
    name: 'Paris Woods',
    major: 'Computer Engineering',
    defaultWorkHours: 20.0,
    recentCourses: ['CDA 3203', 'COP 3530'],
  },
  {
    student_id: 'Z34345109',
    name: 'Joseph Potter',
    major: 'Electrical Engineering',
    defaultWorkHours: 0.0,
    recentCourses: ['EEL 3111', 'MAP 3305'],
  },
  {
    student_id: 'Z42369807',
    name: 'Bellatrix Penderwick',
    major: 'Electrical Engineering',
    defaultWorkHours: 10.0,
    recentCourses: ['PHY 2049'],
  },
  {
    student_id: 'Z23640412',
    name: 'Rosalind Mcclaire',
    major: 'Computer Science',
    defaultWorkHours: 5.0,
    recentCourses: ['COP 3530'],
  },
  {
    student_id: 'Z34567813',
    name: 'Skye Magee',
    major: 'Computer Engineering',
    defaultWorkHours: 12.0,
    recentCourses: ['CDA 3203'],
  },
  {
    student_id: 'Z34254017',
    name: 'Tessa Virtue',
    major: 'Computer Science',
    defaultWorkHours: 25.0,
    recentCourses: ['COT 4400'],
  },
];

export default function App() {
  // --- 1. Real Course & Section State ---
  const [courses, setCourses] = useState<RawCourseRecord[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [coursesError, setCoursesError] = useState<string | null>(null);

  const [selectedCourseCode, setSelectedCourseCode] = useState('');
  const [availableSections, setAvailableSections] = useState<RawSectionRecord[]>([]);
  const [loadingSections, setLoadingSections] = useState(false);
  const [sectionsError, setSectionsError] = useState<string | null>(null);

  // Student's active schedule of real sections
  const [enrolledSections, setEnrolledSections] = useState<RawSectionRecord[]>([]);

  // Demo toggle: show mock schedule data when desired
  const [showDemoSchedule, setShowDemoSchedule] = useState(false);

  // --- 2. Alternatives Search State ---
  const [alternativesTarget, setAlternativesTarget] = useState<RawSectionRecord | null>(null);
  const [alternativesList, setAlternativesList] = useState<RawSectionRecord[]>([]);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);
  const [alternativesError, setAlternativesError] = useState<string | null>(null);

  // --- 3. Course Compatibility Form State ---
  const [compatProfileId, setCompatProfileId] = useState(SYNTHETIC_PROFILES[0].student_id);
  const [compatProposedInput, setCompatProposedInput] = useState('');
  const [compatDifficulty, setCompatDifficulty] = useState(1);
  const [compatSatisfaction, setCompatSatisfaction] = useState<'yes' | 'mostly' | 'no'>('yes');
  const [compatWorkHours, setCompatWorkHours] = useState(5.0);
  const [compatMaxCredits, setCompatMaxCredits] = useState(15.0);
  const [compatRecentInput, setCompatRecentInput] = useState('CDA4240C, CDA4102, MAC2313');

  const [compatResult, setCompatResult] = useState<CompatibilityResponse | null>(null);
  const [loadingCompat, setLoadingCompat] = useState(false);
  const [compatError, setCompatError] = useState<string | null>(null);

  // --- Fetch distinct courses on load ---
  useEffect(() => {
    let isMounted = true;

    getCourses()
      .then((res) => {
        if (!isMounted) return;
        // Deduplicate courses by course code
        const map = new Map<string, RawCourseRecord>();
        for (const item of res.courses) {
          const code = item.COURSE?.trim();
          if (code && !map.has(code)) {
            map.set(code, item);
          }
        }
        const distinctList = Array.from(map.values()).sort((a, b) =>
          a.COURSE.localeCompare(b.COURSE)
        );
        setCourses(distinctList);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to connect to backend';
        setCoursesError(`Backend unavailable (${msg}). Please ensure uvicorn backend.api:app is running.`);
      })
      .finally(() => {
        if (isMounted) setLoadingCourses(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // --- Fetch sections when course selected ---
  const handleSelectCourse = (courseCode: string) => {
    setSelectedCourseCode(courseCode);
    setAvailableSections([]);
    setSectionsError(null);

    if (!courseCode) return;

    setLoadingSections(true);
    getSections(courseCode)
      .then((res) => {
        setAvailableSections(res.sections);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Error fetching sections';
        setSectionsError(msg);
      })
      .finally(() => {
        setLoadingSections(false);
      });
  };

  // --- Add section to schedule ---
  const handleAddSection = (section: RawSectionRecord) => {
    if (enrolledSections.some((s) => String(s.CRN) === String(section.CRN))) {
      return; // already added
    }
    const updated = [...enrolledSections, section];
    setEnrolledSections(updated);

    // Auto-update compatibility proposed courses list
    const codes = Array.from(new Set(updated.map((s) => s.COURSE.trim())));
    setCompatProposedInput(codes.join(', '));
  };

  // --- Remove section from schedule ---
  const handleRemoveSection = (crn: number | string) => {
    const updated = enrolledSections.filter((s) => String(s.CRN) !== String(crn));
    setEnrolledSections(updated);
    const codes = Array.from(new Set(updated.map((s) => s.COURSE.trim())));
    setCompatProposedInput(codes.join(', '));
    if (alternativesTarget && String(alternativesTarget.CRN) === String(crn)) {
      setAlternativesTarget(null);
      setAlternativesList([]);
    }
  };

  // --- Open Find Alternatives ---
  const handleFindAlternatives = (target: RawSectionRecord) => {
    setAlternativesTarget(target);
    setAlternativesList([]);
    setAlternativesError(null);
    setLoadingAlternatives(true);

    const otherCrns = enrolledSections
      .map((s) => s.CRN)
      .filter((crn) => String(crn) !== String(target.CRN));

    getAlternatives(target.CRN, otherCrns)
      .then((res) => {
        setAlternativesList(res.alternatives);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to search alternative sections';
        setAlternativesError(msg);
      })
      .finally(() => {
        setLoadingAlternatives(false);
      });
  };

  // --- Replace section with alternative ---
  const handleSwapAlternative = (newSection: RawSectionRecord) => {
    if (!alternativesTarget) return;
    const targetCrnStr = String(alternativesTarget.CRN);
    const updated = enrolledSections.map((s) =>
      String(s.CRN) === targetCrnStr ? newSection : s
    );
    setEnrolledSections(updated);
    setAlternativesTarget(null);
    setAlternativesList([]);
  };

  // --- Map enrolled sections to calendar & unscheduled lists ---
  const { inGridSections, unscheduledSections } = useMemo(() => {
    const inGrid: CourseSection[] = [];
    const unscheduled: Array<{ raw: RawSectionRecord; note: string }> = [];

    for (const raw of enrolledSections) {
      const mapped = mapBackendSectionToCourseSection(raw);
      if (mapped.isUnscheduled) {
        unscheduled.push({ raw, note: mapped.scheduleNote });
      } else {
        inGrid.push(mapped.section);
      }
    }
    return { inGridSections: inGrid, unscheduledSections: unscheduled };
  }, [enrolledSections]);

  // Calendar display target: either real in-grid sections or mock demo sections
  const displaySections: CourseSection[] = showDemoSchedule ? MOCK_SECTIONS : inGridSections;
  const conflictingIds = useMemo(
    () => getConflictingSectionIds(displaySections),
    [displaySections]
  );
  const hours = Array.from({ length: 11 }, (_, i) => i + 8);

  // --- Profile Selection Change ---
  const handleProfileChange = (studentId: string) => {
    setCompatProfileId(studentId);
    const prof = SYNTHETIC_PROFILES.find((p) => p.student_id === studentId);
    if (prof) {
      setCompatWorkHours(prof.defaultWorkHours);
      if (prof.recentCourses.length > 0) {
        setCompatRecentInput(prof.recentCourses.join(', '));
      }
    }
  };

  // --- Run Compatibility Check ---
  const handleRunCompatibility = (e: React.FormEvent) => {
    e.preventDefault();
    setCompatError(null);
    setCompatResult(null);

    const proposedList = compatProposedInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    if (proposedList.length === 0) {
      setCompatError('Please specify at least one proposed course code (e.g., COP 3530).');
      return;
    }

    const recentList = compatRecentInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    setLoadingCompat(true);
    checkCompatibility({
      student_id: compatProfileId,
      proposed_courses: proposedList,
      recent_difficulty: Number(compatDifficulty),
      satisfied_with_performance: compatSatisfaction,
      work_hours: Number(compatWorkHours),
      preferred_max_credits: compatMaxCredits ? Number(compatMaxCredits) : null,
      recent_courses: recentList.length > 0 ? recentList : null,
    })
      .then((res) => {
        setCompatResult(res);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && typeof err.data === 'object' && err.data !== null) {
          const detail = (err.data as { detail: unknown }).detail;
          if (typeof detail === 'object' && detail !== null) {
            setCompatResult(detail as CompatibilityResponse);
            return;
          }
        }
        const msg = err instanceof Error ? err.message : 'Compatibility evaluation failed';
        setCompatError(msg);
      })
      .finally(() => {
        setLoadingCompat(false);
      });
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#f3f4f6', padding: '2rem' }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'grid', gap: '2rem', textAlign: 'left' }}>
        
        {/* Header */}
        <header style={{ borderBottom: '2px solid #e5e7eb', paddingBottom: '1rem' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: '#1f2937' }}>
            SmartAdvisor Integrated Dashboard
          </h1>
          <p style={{ color: '#4b5563', fontSize: '0.875rem' }}>
            Real course catalog, section scheduling, conflict resolution & compatibility support
          </p>
        </header>

        {/* 1. Real Course Selection & Section Browser */}
        <section style={{ padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.5rem', color: '#111827' }}>
            1. Real Course Catalog & Section Search
          </h2>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1rem' }}>
            Data source: Florida Atlantic University file-backed catalog (<code>data/FAU_Courses.xlsx</code>).
          </p>

          {coursesError && (
            <div style={{ padding: '0.75rem', backgroundColor: '#fee2e2', border: '1px solid #ef4444', color: '#991b1b', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.875rem' }}>
              {coursesError}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                Select Course ({courses.length > 0 ? `${courses.length} courses loaded` : 'Loading...'})
              </label>
              <select
                id="course-select-dropdown"
                value={selectedCourseCode}
                onChange={(e) => handleSelectCourse(e.target.value)}
                disabled={loadingCourses || courses.length === 0}
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
              >
                <option value="">-- Choose a Course to View Sections --</option>
                {courses.map((c) => (
                  <option key={c.COURSE} value={c.COURSE}>
                    {c.COURSE} — {c.TITLE}
                  </option>
                ))}
              </select>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.75rem', color: '#6b7280', alignSelf: 'center' }}>Quick select:</span>
                {['CAP 4773', 'COP 2220', 'CDA 4240C', 'MAC 2313'].map((code) => (
                  <button
                    key={code}
                    type="button"
                    id={`quick-select-${code.replace(/\s+/g, '-')}`}
                    onClick={() => handleSelectCourse(code)}
                    style={{
                      padding: '0.2rem 0.5rem',
                      fontSize: '0.75rem',
                      borderRadius: '4px',
                      border: '1px solid #d1d5db',
                      backgroundColor: selectedCourseCode === code ? '#2563eb' : '#f3f4f6',
                      color: selectedCourseCode === code ? '#ffffff' : '#374151',
                      cursor: 'pointer',
                    }}
                  >
                    {code}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Available Sections for Selected Course */}
          {selectedCourseCode && (
            <div style={{ marginTop: '1.5rem', borderTop: '1px solid #f3f4f6', paddingTop: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                Available Sections for {selectedCourseCode}
              </h3>
              {loadingSections && <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>Loading sections from backend...</p>}
              {sectionsError && <p style={{ fontSize: '0.875rem', color: '#dc2626' }}>{sectionsError}</p>}
              {!loadingSections && availableSections.length === 0 && !sectionsError && (
                <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>No active sections found for this course.</p>
              )}

              {availableSections.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem', marginTop: '0.5rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                        <th style={{ padding: '0.5rem' }}>CRN</th>
                        <th style={{ padding: '0.5rem' }}>Sec</th>
                        <th style={{ padding: '0.5rem' }}>Days & Time</th>
                        <th style={{ padding: '0.5rem' }}>Modality</th>
                        <th style={{ padding: '0.5rem' }}>Campus</th>
                        <th style={{ padding: '0.5rem' }}>Seats</th>
                        <th style={{ padding: '0.5rem' }}>Instructor</th>
                        <th style={{ padding: '0.5rem' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {availableSections.map((sec) => {
                        const isEnrolled = enrolledSections.some((s) => String(s.CRN) === String(sec.CRN));
                        return (
                          <tr key={String(sec.CRN)} style={{ borderBottom: '1px solid #f3f4f6' }}>
                            <td style={{ padding: '0.5rem', fontWeight: '600' }}>{String(sec.CRN)}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.SECT}</td>
                            <td style={{ padding: '0.5rem' }}>{formatMeetingDisplay(sec)}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.METHOD || 'In-Person'}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.CAMPUS || '—'}</td>
                            <td style={{ padding: '0.5rem', color: Number(sec['ENRL REMN']) <= 0 ? '#dc2626' : '#16a34a' }}>
                              {String(sec['ENRL REMN'] ?? '0')}
                            </td>
                            <td style={{ padding: '0.5rem' }}>{sec.INSTRUCTOR || 'TBA'}</td>
                            <td style={{ padding: '0.5rem' }}>
                              <button
                                type="button"
                                onClick={() => handleAddSection(sec)}
                                disabled={isEnrolled}
                                style={{
                                  padding: '4px 10px',
                                  fontSize: '0.75rem',
                                  backgroundColor: isEnrolled ? '#9ca3af' : '#2563eb',
                                  color: '#ffffff',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: isEnrolled ? 'not-allowed' : 'pointer',
                                }}
                              >
                                {isEnrolled ? 'Added' : '+ Add to Schedule'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>

        {/* 2. Schedule Calendar & Alternatives */}
        <section style={{ padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#111827' }}>
                2. Active Weekly Course Schedule
              </h2>
              <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
                {showDemoSchedule
                  ? '(Demonstration Mode — Displaying simulated test schedule)'
                  : enrolledSections.length === 0
                  ? 'No real sections added yet. Select a course above to add sections to your schedule.'
                  : `${enrolledSections.length} real course section(s) currently selected.`}
              </p>
            </div>
            
            {/* Demo Toggle */}
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: '#4b5563', cursor: 'pointer', backgroundColor: '#f9fafb', padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
              <input
                type="checkbox"
                checked={showDemoSchedule}
                onChange={(e) => setShowDemoSchedule(e.target.checked)}
              />
              Show Demonstration Data (Simulated Mocks)
            </label>
          </div>

          {/* Enrolled Sections Summary Bar */}
          {!showDemoSchedule && enrolledSections.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#166534', marginBottom: '0.5rem' }}>
                Enrolled Sections:
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {enrolledSections.map((sec) => (
                  <div
                    key={String(sec.CRN)}
                    style={{
                      padding: '4px 8px',
                      backgroundColor: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <strong>{sec.COURSE}</strong> (CRN {String(sec.CRN)})
                    <button
                      type="button"
                      title="Find Alternatives"
                      onClick={() => handleFindAlternatives(sec)}
                      style={{ border: 'none', background: '#dbeafe', color: '#1e40af', padding: '2px 6px', borderRadius: '2px', cursor: 'pointer', fontSize: '10px' }}
                    >
                      Alternatives
                    </button>
                    <button
                      type="button"
                      title="Remove"
                      onClick={() => handleRemoveSection(sec.CRN)}
                      style={{ border: 'none', background: '#fee2e2', color: '#991b1b', padding: '2px 6px', borderRadius: '2px', cursor: 'pointer', fontSize: '10px' }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Weekly Calendar Grid (8:00 AM to 6:00 PM) */}
          <div style={{ display: 'grid', gridTemplateColumns: '80px repeat(5, 1fr)', border: '1px solid #e5e7eb' }}>
            <div style={{ padding: '0.5rem', fontWeight: 'bold', borderRight: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
              Time
            </div>
            {DAYS.map((d) => (
              <div key={d} style={{ padding: '0.5rem', fontWeight: 'bold', textAlign: 'center', borderRight: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                {d}
              </div>
            ))}

            <div style={{ borderRight: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
              {hours.map((h) => (
                <div key={h} style={{ height: '48px', borderBottom: '1px solid #e5e7eb', fontSize: '0.75rem', padding: '2px' }}>
                  {h}:00
                </div>
              ))}
            </div>

            {DAYS.map((day) => (
              <div key={day} style={{ position: 'relative', borderRight: '1px solid #e5e7eb', height: '528px' }}>
                {hours.map((h) => (
                  <div key={h} style={{ height: '48px', borderBottom: '1px solid #f3f4f6' }} />
                ))}

                {displaySections.flatMap((sec) =>
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
                            width: '92%',
                            left: '4%',
                            ...stylePos,
                            padding: '6px',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            border: isConflict ? '1px solid #ef4444' : '1px solid #60a5fa',
                            backgroundColor: isConflict ? '#fef2f2' : '#eff6ff',
                            color: isConflict ? '#991b1b' : '#1e40af',
                            boxSizing: 'border-box',
                            overflow: 'hidden',
                          }}
                        >
                          <div style={{ fontWeight: 'bold' }}>{sec.courseCode}</div>
                          <div style={{ fontSize: '10px', opacity: 0.85 }}>{sec.title}</div>
                          <div style={{ fontSize: '10px', marginTop: '2px' }}>
                            {m.startTime} - {m.endTime}
                          </div>
                          {isConflict && (
                            <span style={{ display: 'inline-block', marginTop: '2px', backgroundColor: '#dc2626', color: '#fff', padding: '1px 4px', borderRadius: '2px', fontSize: '9px', fontWeight: 'bold' }}>
                              ⚠️ Time Conflict
                            </span>
                          )}
                          {!showDemoSchedule && sec.raw && (
                            <button
                              type="button"
                              onClick={() => handleFindAlternatives(sec.raw!)}
                              style={{
                                display: 'block',
                                marginTop: '4px',
                                border: 'none',
                                background: '#3b82f6',
                                color: '#fff',
                                padding: '2px 4px',
                                borderRadius: '2px',
                                fontSize: '9px',
                                cursor: 'pointer',
                              }}
                            >
                              Find Alternatives
                            </button>
                          )}
                        </div>
                      );
                    })
                )}
              </div>
            ))}
          </div>

          {/* Unscheduled / Online / Evening Courses Panel */}
          {!showDemoSchedule && unscheduledSections.length > 0 && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.5rem' }}>
                Enrolled Sections Outside Standard Day Calendar:
              </h3>
              <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem' }}>
                Sections without fixed daytime meeting times (such as fully online asynchronous classes or evening offerings starting after 6:00 PM) are preserved below:
              </p>
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                {unscheduledSections.map(({ raw, note }) => (
                  <div
                    key={String(raw.CRN)}
                    style={{
                      padding: '0.5rem',
                      backgroundColor: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '4px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.8125rem',
                    }}
                  >
                    <div>
                      <strong>{raw.COURSE}</strong> — {raw.TITLE} (CRN {String(raw.CRN)}, Sec {raw.SECT})
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{note}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        type="button"
                        onClick={() => handleFindAlternatives(raw)}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                      >
                        Alternatives
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveSection(raw.CRN)}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alternative Section Finder Dialog / Drawer */}
          {alternativesTarget && (
            <div style={{ marginTop: '1.5rem', padding: '1.25rem', backgroundColor: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 'bold', color: '#1e3a8a' }}>
                  Alternative Sections for {alternativesTarget.COURSE} (Replacing CRN {String(alternativesTarget.CRN)})
                </h3>
                <button
                  type="button"
                  onClick={() => setAlternativesTarget(null)}
                  style={{ border: 'none', background: 'transparent', fontSize: '1.25rem', cursor: 'pointer', color: '#6b7280' }}
                >
                  ✕
                </button>
              </div>

              <p style={{ fontSize: '0.8125rem', color: '#1e40af', marginBottom: '0.75rem' }}>
                Queried backend endpoint: <code>GET /alternatives?crn={String(alternativesTarget.CRN)}</code>. Returns sections of the same course in the same term that do not conflict with your other selected classes.
              </p>

              {loadingAlternatives && <p style={{ fontSize: '0.875rem', color: '#2563eb' }}>Searching alternative sections...</p>}
              {alternativesError && <p style={{ fontSize: '0.875rem', color: '#dc2626' }}>{alternativesError}</p>}
              {!loadingAlternatives && alternativesList.length === 0 && !alternativesError && (
                <p style={{ fontSize: '0.875rem', color: '#4b5563' }}>
                  No non-conflicting replacement sections found with open seats in the prototype dataset.
                </p>
              )}

              {alternativesList.length > 0 && (
                <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.5rem' }}>
                  {alternativesList.map((alt) => (
                    <div
                      key={String(alt.CRN)}
                      style={{
                        padding: '0.75rem',
                        backgroundColor: '#ffffff',
                        border: '1px solid #bfdbfe',
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.8125rem',
                      }}
                    >
                      <div>
                        <strong>Section {alt.SECT}</strong> (CRN {String(alt.CRN)}) — {formatMeetingDisplay(alt)}
                        <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                          Instructor: {alt.INSTRUCTOR || 'TBA'} | Campus: {alt.CAMPUS || 'Main'} | Seats Remaining: {String(alt['ENRL REMN'] ?? 0)}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleSwapAlternative(alt)}
                        style={{
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          backgroundColor: '#16a34a',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontWeight: '600',
                        }}
                      >
                        Swap with this Section
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        {/* 3. Course Compatibility Evaluator */}
        <section style={{ padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.5rem', color: '#111827' }}>
            3. Course Compatibility & Workload Screener
          </h2>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1rem' }}>
            Authoritative backend endpoint: <code>POST /compatibility</code>. Evaluates course load difficulty and historical combinations using synthetic student profiles.
          </p>

          <form onSubmit={handleRunCompatibility} style={{ display: 'grid', gap: '1rem', maxWidth: '800px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Synthetic Student Profile
                </label>
                <select
                  value={compatProfileId}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                >
                  {SYNTHETIC_PROFILES.map((p) => (
                    <option key={p.student_id} value={p.student_id}>
                      {p.name} ({p.student_id}) — {p.major}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Proposed Courses (comma-separated)
                </label>
                <input
                  type="text"
                  value={compatProposedInput}
                  onChange={(e) => setCompatProposedInput(e.target.value)}
                  placeholder="e.g., COP4331, MAP3305, CDA4630"
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Recent Difficulty (1 easy to 5 hard)
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={compatDifficulty}
                  onChange={(e) => setCompatDifficulty(Number(e.target.value))}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Satisfied with Past Performance?
                </label>
                <select
                  value={compatSatisfaction}
                  onChange={(e) => setCompatSatisfaction(e.target.value as 'yes' | 'mostly' | 'no')}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                >
                  <option value="yes">Yes</option>
                  <option value="mostly">Mostly</option>
                  <option value="no">No</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Work Hours / Week
                </label>
                <input
                  type="number"
                  min="0"
                  max="80"
                  step="0.5"
                  value={compatWorkHours}
                  onChange={(e) => setCompatWorkHours(Number(e.target.value))}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                  Max Target Credits
                </label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={compatMaxCredits}
                  onChange={(e) => setCompatMaxCredits(Number(e.target.value))}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                Recent Courses Completed (optional)
              </label>
              <input
                type="text"
                value={compatRecentInput}
                onChange={(e) => setCompatRecentInput(e.target.value)}
                placeholder="e.g., CDA4240C, CDA4102, MAC2313"
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
              />
            </div>

            <button
              type="submit"
              disabled={loadingCompat}
              style={{
                padding: '0.625rem 1.25rem',
                backgroundColor: loadingCompat ? '#9ca3af' : '#4f46e5',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '0.875rem',
                fontWeight: '600',
                cursor: loadingCompat ? 'not-allowed' : 'pointer',
                justifySelf: 'start',
              }}
            >
              {loadingCompat ? 'Evaluating Compatibility...' : 'Evaluate Course Compatibility'}
            </button>
          </form>

          {compatError && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#fee2e2', border: '1px solid #ef4444', color: '#991b1b', borderRadius: '4px', fontSize: '0.875rem' }}>
              {compatError}
            </div>
          )}

          {compatResult && (
            <div style={{ marginTop: '1.5rem', padding: '1.25rem', backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#0f172a' }}>
                  Compatibility Result for {compatResult.student_name} ({compatResult.major})
                </h3>
                <span
                  style={{
                    padding: '4px 12px',
                    borderRadius: '9999px',
                    fontSize: '0.8125rem',
                    fontWeight: 'bold',
                    backgroundColor:
                      compatResult.overall_risk === 'Low'
                        ? '#dcfce7'
                        : compatResult.overall_risk === 'Medium'
                        ? '#fef9c3'
                        : '#fee2e2',
                    color:
                      compatResult.overall_risk === 'Low'
                        ? '#166534'
                        : compatResult.overall_risk === 'Medium'
                        ? '#854d0e'
                        : '#991b1b',
                  }}
                >
                  Overall Workload Risk: {compatResult.overall_risk}
                </span>
              </div>

              <div style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>
                <strong>Proposed Credits:</strong> {compatResult.proposed_credits} | <strong>Courses:</strong> {compatResult.proposed_courses?.join(', ')}
              </div>

              {compatResult.recommendations && compatResult.recommendations.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <strong>Recommendations:</strong>
                  <ul style={{ margin: '0.25rem 0 0 1.25rem', padding: 0, fontSize: '0.8125rem' }}>
                    {compatResult.recommendations.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {compatResult.matched_combinations && compatResult.matched_combinations.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <strong>Combination Analysis:</strong>
                  <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.25rem' }}>
                    {compatResult.matched_combinations.map((comb, i) => (
                      <div key={i} style={{ padding: '0.5rem', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '4px', fontSize: '0.8125rem' }}>
                        <div><strong>Pair:</strong> {comb.courses.join(' + ')} | <strong>Category:</strong> {comb.risk_category} ({comb.severity})</div>
                        <div style={{ color: '#475569', marginTop: '2px' }}>{comb.explanation}</div>
                        {comb.recommended_action && <div style={{ color: '#0369a1', marginTop: '2px' }}>Action: {comb.recommended_action}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {compatResult.repeat_courses && compatResult.repeat_courses.length > 0 && (
                <div style={{ marginBottom: '0.5rem', color: '#b45309', fontSize: '0.8125rem' }}>
                  ⚠️ <strong>Repeat Course Warning:</strong> {compatResult.repeat_courses.join(', ')}
                </div>
              )}

              {compatResult.disclaimer && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic', borderTop: '1px solid #e2e8f0', paddingTop: '0.5rem' }}>
                  {compatResult.disclaimer}
                </p>
              )}
            </div>
          )}
        </section>

        {/* 4. Conversational Planning Assistant (Deterministic Prototype) */}
        <ConversationalAssistant
          defaultProfileId={compatProfileId}
          defaultWorkHours={compatWorkHours}
          defaultDifficulty={compatDifficulty}
          defaultSatisfaction={compatSatisfaction}
          defaultRecentCourses={compatRecentInput}
        />

        {/* 5. Online Course Override Guidance (Preserved) */}
        <OnlineOverrideEvaluator />
      </div>
    </main>
  );
}