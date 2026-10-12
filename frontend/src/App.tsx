import { useState, useEffect, useMemo, useRef } from 'react';
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
  groupRawSectionsByCrn,
  mapGroupedSectionToCourseSection,
  formatGroupedMeetingDisplay,
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

  // Student's proposed schedule of selected sections
  const [selectedSections, setSelectedSections] = useState<RawSectionRecord[]>([]);

  // Demo toggle: show mock schedule data when desired
  const [showDemoSchedule, setShowDemoSchedule] = useState(false);

  // --- 2. Alternatives Search State ---
  const [alternativesTarget, setAlternativesTarget] = useState<RawSectionRecord | null>(null);
  const [alternativesList, setAlternativesList] = useState<RawSectionRecord[]>([]);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);
  const [alternativesError, setAlternativesError] = useState<string | null>(null);

  // Request race-condition tracking refs
  const sectionsRequestIdRef = useRef(0);
  const alternativesRequestIdRef = useRef(0);

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

  // --- Fetch sections when course selected (with race condition prevention) ---
  const handleSelectCourse = (courseCode: string) => {
    const reqId = ++sectionsRequestIdRef.current;
    setSelectedCourseCode(courseCode);
    setAvailableSections([]);
    setSectionsError(null);

    if (!courseCode) {
      setLoadingSections(false);
      return;
    }

    setLoadingSections(true);
    getSections(courseCode)
      .then((res) => {
        if (reqId !== sectionsRequestIdRef.current) return;
        setAvailableSections(res.sections);
      })
      .catch((err: unknown) => {
        if (reqId !== sectionsRequestIdRef.current) return;
        const msg = err instanceof Error ? err.message : 'Error fetching sections';
        setSectionsError(msg);
      })
      .finally(() => {
        if (reqId === sectionsRequestIdRef.current) {
          setLoadingSections(false);
        }
      });
  };

  // --- Group raw available sections by CRN to preserve multi-meeting sections ---
  const groupedAvailableSections = useMemo(
    () => groupRawSectionsByCrn(availableSections),
    [availableSections]
  );

  // --- Add grouped section records to proposed schedule ---
  const handleAddSectionGroup = (records: RawSectionRecord[]) => {
    if (!records || records.length === 0) return;
    const crnStr = String(records[0].CRN);
    if (selectedSections.some((s) => String(s.CRN) === crnStr)) {
      return; // already added
    }
    const updated = [...selectedSections, ...records];
    setSelectedSections(updated);

    // Invalidate open alternatives as selected schedule has changed
    if (alternativesTarget) {
      setAlternativesTarget(null);
      setAlternativesList([]);
      setAlternativesError(null);
    }

    // Auto-update compatibility proposed courses list
    const codes = Array.from(new Set(updated.map((s) => s.COURSE.trim())));
    setCompatProposedInput(codes.join(', '));
  };

  // --- Remove all section records for a CRN from proposed schedule ---
  const handleRemoveSection = (crn: number | string) => {
    const crnStr = String(crn);
    const updated = selectedSections.filter((s) => String(s.CRN) !== crnStr);
    setSelectedSections(updated);

    if (alternativesTarget && String(alternativesTarget.CRN) === crnStr) {
      setAlternativesTarget(null);
      setAlternativesList([]);
      setAlternativesError(null);
    } else if (alternativesTarget) {
      // Invalidate open alternatives as conflicting set changed
      setAlternativesTarget(null);
      setAlternativesList([]);
    }

    const codes = Array.from(new Set(updated.map((s) => s.COURSE.trim())));
    setCompatProposedInput(codes.join(', '));
  };

  // --- Open Find Alternatives (with race condition prevention) ---
  const handleFindAlternatives = (target: RawSectionRecord) => {
    const reqId = ++alternativesRequestIdRef.current;
    setAlternativesTarget(target);
    setAlternativesList([]);
    setAlternativesError(null);
    setLoadingAlternatives(true);

    const otherCrns = Array.from(
      new Set(
        selectedSections
          .map((s) => String(s.CRN))
          .filter((crn) => crn !== String(target.CRN))
      )
    );

    getAlternatives(target.CRN, otherCrns)
      .then((res) => {
        if (reqId !== alternativesRequestIdRef.current) return;
        setAlternativesList(res.alternatives);
      })
      .catch((err: unknown) => {
        if (reqId !== alternativesRequestIdRef.current) return;
        const msg = err instanceof Error ? err.message : 'Failed to search alternative sections';
        setAlternativesError(msg);
      })
      .finally(() => {
        if (reqId === alternativesRequestIdRef.current) {
          setLoadingAlternatives(false);
        }
      });
  };

  // --- Group alternatives list by CRN ---
  const groupedAlternativesList = useMemo(
    () => groupRawSectionsByCrn(alternativesList),
    [alternativesList]
  );

  // --- Replace section with alternative group ---
  const handleSwapAlternativeGroup = (newRecords: RawSectionRecord[]) => {
    if (!alternativesTarget || !newRecords.length) return;
    const targetCrnStr = String(alternativesTarget.CRN);
    const filtered = selectedSections.filter((s) => String(s.CRN) !== targetCrnStr);
    const updated = [...filtered, ...newRecords];
    setSelectedSections(updated);
    setAlternativesTarget(null);
    setAlternativesList([]);
    setAlternativesError(null);

    const codes = Array.from(new Set(updated.map((s) => s.COURSE.trim())));
    setCompatProposedInput(codes.join(', '));
  };

  // --- Map selected sections into calendar grid, out-of-grid timed, async, and TBA ---
  const { inGridSections, outOfGridTimedSections, asynchronousSections, unknownTbaSections } = useMemo(() => {
    const grouped = groupRawSectionsByCrn(selectedSections);
    const inGrid: CourseSection[] = [];
    const outOfGridTimed: CourseSection[] = [];
    const asyncSections: CourseSection[] = [];
    const unknownSections: CourseSection[] = [];

    for (const group of grouped) {
      const mapped = mapGroupedSectionToCourseSection(group);
      if (mapped.section.meetingCategory === 'in_grid') {
        inGrid.push(mapped.section);
      } else if (mapped.section.meetingCategory === 'out_of_grid_timed') {
        outOfGridTimed.push(mapped.section);
      } else if (mapped.section.meetingCategory === 'asynchronous') {
        asyncSections.push(mapped.section);
      } else {
        unknownSections.push(mapped.section);
      }
    }

    return {
      inGridSections: inGrid,
      outOfGridTimedSections: outOfGridTimed,
      asynchronousSections: asyncSections,
      unknownTbaSections: unknownSections,
    };
  }, [selectedSections]);

  // Calendar display target: either real in-grid sections or mock demo sections
  const displaySections: CourseSection[] = showDemoSchedule ? MOCK_SECTIONS : inGridSections;

  // Conflict detection checks all timed sections (in-grid and out-of-grid)
  const allTimedSections = useMemo(
    () => [...inGridSections, ...outOfGridTimedSections],
    [inGridSections, outOfGridTimedSections]
  );

  const conflictingIds = useMemo(
    () => (showDemoSchedule ? getConflictingSectionIds(MOCK_SECTIONS) : getConflictingSectionIds(allTimedSections)),
    [showDemoSchedule, allTimedSections]
  );

  const hours = Array.from({ length: 11 }, (_, i) => i + 8);

  // Distinct unique selected CRNs for summary badges
  const distinctSelectedSections = useMemo(() => {
    return groupRawSectionsByCrn(selectedSections).map((group) => group[0]);
  }, [selectedSections]);

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
        if (res && res.success) {
          setCompatResult(res);
        } else {
          setCompatError((res as { error?: string })?.error || 'Compatibility evaluation was not successful.');
        }
      })
      .catch((err: unknown) => {
        const msg =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
            ? err.message
            : 'Compatibility evaluation failed';
        setCompatError(msg);
        setCompatResult(null);
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
              {!loadingSections && groupedAvailableSections.length === 0 && !sectionsError && (
                <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>No active sections found for this course.</p>
              )}

              {groupedAvailableSections.length > 0 && (
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
                      {groupedAvailableSections.map((secRecords) => {
                        const sec = secRecords[0];
                        const crnStr = String(sec.CRN);
                        const isSelected = selectedSections.some((s) => String(s.CRN) === crnStr);
                        return (
                          <tr key={crnStr} style={{ borderBottom: '1px solid #f3f4f6' }}>
                            <td style={{ padding: '0.5rem', fontWeight: '600' }}>{crnStr}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.SECT}</td>
                            <td style={{ padding: '0.5rem' }}>{formatGroupedMeetingDisplay(secRecords)}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.METHOD || 'In-Person'}</td>
                            <td style={{ padding: '0.5rem' }}>{sec.CAMPUS || '—'}</td>
                            <td style={{ padding: '0.5rem', color: Number(sec['ENRL REMN']) <= 0 ? '#dc2626' : '#16a34a' }}>
                              {String(sec['ENRL REMN'] ?? '0')}
                            </td>
                            <td style={{ padding: '0.5rem' }}>{sec.INSTRUCTOR || 'TBA'}</td>
                            <td style={{ padding: '0.5rem' }}>
                              <button
                                type="button"
                                onClick={() => handleAddSectionGroup(secRecords)}
                                disabled={isSelected}
                                style={{
                                  padding: '4px 10px',
                                  fontSize: '0.75rem',
                                  backgroundColor: isSelected ? '#9ca3af' : '#2563eb',
                                  color: '#ffffff',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: isSelected ? 'not-allowed' : 'pointer',
                                }}
                              >
                                {isSelected ? 'Selected' : '+ Add to Schedule'}
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
                2. Proposed Schedule & Conflict Resolution
              </h2>
              <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
                {showDemoSchedule
                  ? '(Demonstration Mode — Displaying simulated test schedule)'
                  : distinctSelectedSections.length === 0
                  ? 'No sections selected yet. Choose a course above to add sections to your proposed schedule.'
                  : `${distinctSelectedSections.length} course section(s) currently selected for planning.`}
              </p>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                Adding or swapping sections updates your preliminary planning schedule; it does not enroll a student in FAU systems.
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

          {/* Selected Sections Summary Bar */}
          {!showDemoSchedule && distinctSelectedSections.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#166534', marginBottom: '0.5rem' }}>
                Proposed Schedule (Selected Sections):
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {distinctSelectedSections.map((sec) => {
                  const crnStr = String(sec.CRN);
                  const isConflict = conflictingIds.has(crnStr);
                  return (
                    <div
                      key={crnStr}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#ffffff',
                        border: isConflict ? '1px solid #ef4444' : '1px solid #cbd5e1',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <strong>{sec.COURSE}</strong> (CRN {crnStr})
                      {isConflict && (
                        <span style={{ backgroundColor: '#fee2e2', color: '#b91c1c', padding: '1px 4px', borderRadius: '2px', fontSize: '10px', fontWeight: 'bold' }}>
                          ⚠️ Conflict
                        </span>
                      )}
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
                  );
                })}
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

          {/* Sections Outside Standard Day Calendar (Evening, Weekend, Asynchronous, TBA) */}
          {!showDemoSchedule && (outOfGridTimedSections.length > 0 || asynchronousSections.length > 0 || unknownTbaSections.length > 0) && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.5rem' }}>
                Selected Sections Outside Standard Daytime Calendar (8 AM – 6 PM):
              </h3>
              <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem' }}>
                Timed evening/weekend offerings participate in conflict detection. Fully online asynchronous or TBA sections are listed separately.
              </p>

              {/* 1. Out-of-Grid Timed Sections (Evening / Weekend) */}
              {outOfGridTimedSections.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: '#1e293b', marginBottom: '0.35rem' }}>
                    Evening / Weekend Timed Sections (Conflict Check Active):
                  </div>
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
                    {outOfGridTimedSections.map((sec) => {
                      const isConflict = conflictingIds.has(sec.id);
                      return (
                        <div
                          key={sec.id}
                          style={{
                            padding: '0.5rem',
                            backgroundColor: isConflict ? '#fef2f2' : '#ffffff',
                            border: isConflict ? '1px solid #f87171' : '1px solid #cbd5e1',
                            borderRadius: '4px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            fontSize: '0.8125rem',
                          }}
                        >
                          <div>
                            <strong>{sec.courseCode}</strong> — {sec.title} (CRN {sec.id}{sec.sect ? `, Sec ${sec.sect}` : ''})
                            <div style={{ fontSize: '0.75rem', color: isConflict ? '#b91c1c' : '#64748b' }}>
                              {sec.scheduleNote}
                              {isConflict && ' — ⚠️ OVERLAPS WITH ANOTHER SCHEDULED SECTION'}
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            {sec.raw && (
                              <button
                                type="button"
                                onClick={() => handleFindAlternatives(sec.raw!)}
                                style={{ padding: '4px 8px', fontSize: '0.75rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                              >
                                Alternatives
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleRemoveSection(sec.id)}
                              style={{ padding: '4px 8px', fontSize: '0.75rem', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 2. Asynchronous Online Sections */}
              {asynchronousSections.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: '#1e293b', marginBottom: '0.35rem' }}>
                    Asynchronous Distance Learning (No Fixed Meeting Times):
                  </div>
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
                    {asynchronousSections.map((sec) => (
                      <div
                        key={sec.id}
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
                          <strong>{sec.courseCode}</strong> — {sec.title} (CRN {sec.id})
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{sec.scheduleNote}</div>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {sec.raw && (
                            <button
                              type="button"
                              onClick={() => handleFindAlternatives(sec.raw!)}
                              style={{ padding: '4px 8px', fontSize: '0.75rem', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                            >
                              Alternatives
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleRemoveSection(sec.id)}
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

              {/* 3. Unknown / TBA Sections */}
              {unknownTbaSections.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: '#1e293b', marginBottom: '0.35rem' }}>
                    Meeting Schedule TBA / Unspecified (Conflict Clearance Unavailable):
                  </div>
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
                    {unknownTbaSections.map((sec) => (
                      <div
                        key={sec.id}
                        style={{
                          padding: '0.5rem',
                          backgroundColor: '#fffbeb',
                          border: '1px solid #fde68a',
                          borderRadius: '4px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          fontSize: '0.8125rem',
                        }}
                      >
                        <div>
                          <strong>{sec.courseCode}</strong> — {sec.title} (CRN {sec.id})
                          <div style={{ fontSize: '0.75rem', color: '#b45309' }}>{sec.scheduleNote}</div>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            type="button"
                            onClick={() => handleRemoveSection(sec.id)}
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
                Queried backend endpoint: <code>GET /alternatives?crn={String(alternativesTarget.CRN)}</code>. Returns sections of the same course that do not conflict with your other selected classes.
              </p>

              {loadingAlternatives && <p style={{ fontSize: '0.875rem', color: '#2563eb' }}>Searching alternative sections...</p>}
              {alternativesError && <p style={{ fontSize: '0.875rem', color: '#dc2626' }}>{alternativesError}</p>}
              {!loadingAlternatives && groupedAlternativesList.length === 0 && !alternativesError && (
                <p style={{ fontSize: '0.875rem', color: '#4b5563' }}>
                  No non-conflicting replacement sections found with open seats in the prototype dataset.
                </p>
              )}

              {groupedAlternativesList.length > 0 && (
                <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.5rem' }}>
                  {groupedAlternativesList.map((altRecords) => {
                    const alt = altRecords[0];
                    return (
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
                          <strong>Section {alt.SECT}</strong> (CRN {String(alt.CRN)}) — {formatGroupedMeetingDisplay(altRecords)}
                          <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                            Instructor: {alt.INSTRUCTOR || 'TBA'} | Campus: {alt.CAMPUS || 'Main'} | Seats Remaining: {String(alt['ENRL REMN'] ?? 0)}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSwapAlternativeGroup(altRecords)}
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
                    );
                  })}
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
              <div style={{ marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#0f172a', margin: '0 0 0.5rem 0' }}>
                  Compatibility Result for {compatResult.student_name} ({compatResult.major})
                </h3>
                <div style={{ fontSize: '0.8125rem', color: '#475569' }}>
                  Student ID: {compatResult.student_id} | Proposed Credits: <strong>{compatResult.proposed_credits}</strong>
                  {compatResult.recent_credits !== null && compatResult.recent_credits !== undefined && (
                    <span> | Recent Credits: <strong>{compatResult.recent_credits}</strong></span>
                  )}
                </div>
              </div>

              {/* Primary Engine Assessment */}
              <div style={{ padding: '0.875rem', backgroundColor: '#eff6ff', borderLeft: '4px solid #3b82f6', borderRadius: '4px', marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#1d4ed8' }}>
                  Semester Assessment
                </div>
                <div style={{ fontSize: '0.9375rem', fontWeight: '600', color: '#1e3a8a', marginTop: '0.25rem' }}>
                  {compatResult.assessment}
                </div>
              </div>

              {/* Matched Course Combinations */}
              {compatResult.matched_course_combinations && compatResult.matched_course_combinations.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 'bold', color: '#1e293b', marginBottom: '0.5rem' }}>
                    Matched Course Combinations ({compatResult.matched_course_combinations.length}):
                  </h4>
                  <div style={{ display: 'grid', gap: '0.75rem' }}>
                    {compatResult.matched_course_combinations.map((comb, i) => (
                      <div key={i} style={{ padding: '0.75rem', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.8125rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem', flexWrap: 'wrap', gap: '0.25rem' }}>
                          <strong>Pair: {comb.courses.join(' + ')}</strong>
                          <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#f1f5f9', color: '#334155', fontWeight: '600' }}>
                            {comb.baseline_rating}
                          </span>
                        </div>
                        <p style={{ margin: '0.25rem 0', color: '#334155' }}>{comb.personalized_guidance}</p>
                        {comb.reasoning && (
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                            <em>Reasoning:</em> {comb.reasoning}
                          </div>
                        )}
                        {comb.factors && comb.factors.length > 0 && (
                          <ul style={{ margin: '0.35rem 0 0 1.25rem', padding: 0, fontSize: '0.75rem', color: '#475569' }}>
                            {comb.factors.map((f, fi) => (
                              <li key={fi}>{f}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {compatResult.recommendations && compatResult.recommendations.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 'bold', color: '#1e293b', marginBottom: '0.25rem' }}>
                    Recommendations:
                  </h4>
                  <ul style={{ margin: '0.25rem 0 0 1.25rem', padding: 0, fontSize: '0.8125rem', color: '#334155' }}>
                    {compatResult.recommendations.map((rec, i) => (
                      <li key={i} style={{ marginTop: '0.25rem' }}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Repeat Course Warning */}
              {compatResult.repeat_course_warning && (
                <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '0.8125rem', color: '#92400e' }}>
                  <strong>⚠️ Repeat Course Warning:</strong> {compatResult.repeat_course_warning}
                  {compatResult.previously_completed_courses && compatResult.previously_completed_courses.length > 0 && (
                    <div style={{ marginTop: '0.25rem', fontSize: '0.75rem' }}>
                      Previously completed courses in student history: {compatResult.previously_completed_courses.join(', ')}
                    </div>
                  )}
                </div>
              )}

              {/* Data Warnings */}
              {compatResult.data_warnings && compatResult.data_warnings.length > 0 && (
                <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '0.8125rem', color: '#991b1b' }}>
                  <strong>Data Warnings:</strong>
                  <ul style={{ margin: '0.25rem 0 0 1.25rem', padding: 0, fontSize: '0.75rem' }}>
                    {compatResult.data_warnings.map((dw, i) => (
                      <li key={i}>{dw}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Disclaimer */}
              {compatResult.disclaimer && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic', borderTop: '1px solid #e2e8f0', paddingTop: '0.5rem', margin: '0.75rem 0 0 0' }}>
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