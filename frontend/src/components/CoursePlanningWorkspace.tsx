import { useMemo } from 'react';
import type { RawCourseRecord, RawSectionRecord } from '../services/api';
import { MOCK_SECTIONS } from '../types/schedule';
import {
  DAYS,
  calculateBlockStyle,
  formatGroupedMeetingDisplay,
  getConflictingSectionIds,
  groupRawSectionsByCrn,
  mapGroupedSectionToCourseSection,
  type CourseSection,
} from '../utils/scheduleUtils';

interface Props {
  courses: RawCourseRecord[];
  loadingCourses: boolean;
  coursesError: string | null;
  selectedCourseCode: string;
  onSelectCourse: (courseCode: string) => void;
  availableSections: RawSectionRecord[];
  loadingSections: boolean;
  sectionsError: string | null;
  selectedSections: RawSectionRecord[];
  onAddSectionGroup: (records: RawSectionRecord[]) => void;
  onRemoveSection: (crn: string | number) => void;
  compact?: boolean;
  headingPrefix?: string;
  showDemoSchedule?: boolean;
  onShowDemoScheduleChange?: (show: boolean) => void;
  onFindAlternatives?: (section: RawSectionRecord) => void;
  alternativesTarget?: RawSectionRecord | null;
  alternativesList?: RawSectionRecord[];
  loadingAlternatives?: boolean;
  alternativesError?: string | null;
  onCloseAlternatives?: () => void;
  onSwapAlternativeGroup?: (records: RawSectionRecord[]) => void;
}

const QUICK_COURSES = ['CAP 4773', 'MAP 3305', 'CDA 4240C', 'MAC 2313'];
const hours = Array.from({ length: 11 }, (_, index) => index + 8);

export function CoursePlanningWorkspace({
  courses,
  loadingCourses,
  coursesError,
  selectedCourseCode,
  onSelectCourse,
  availableSections,
  loadingSections,
  sectionsError,
  selectedSections,
  onAddSectionGroup,
  onRemoveSection,
  compact = false,
  headingPrefix = '',
  showDemoSchedule = false,
  onShowDemoScheduleChange,
  onFindAlternatives,
  alternativesTarget = null,
  alternativesList = [],
  loadingAlternatives = false,
  alternativesError = null,
  onCloseAlternatives,
  onSwapAlternativeGroup,
}: Props) {
  const availableGroups = useMemo(() => groupRawSectionsByCrn(availableSections), [availableSections]);
  const selectedGroups = useMemo(() => groupRawSectionsByCrn(selectedSections), [selectedSections]);
  const mappedSections = useMemo(
    () => selectedGroups.map((group) => mapGroupedSectionToCourseSection(group).section),
    [selectedGroups],
  );
  const inGrid = mappedSections.filter((section) => section.meetingCategory === 'in_grid');
  const outsideGrid = mappedSections.filter((section) => section.meetingCategory !== 'in_grid');
  const displaySections: CourseSection[] = showDemoSchedule ? MOCK_SECTIONS : inGrid;
  const conflictSections = showDemoSchedule ? MOCK_SECTIONS : mappedSections;
  const conflictingIds = getConflictingSectionIds(conflictSections);
  const alternativeGroups = useMemo(() => groupRawSectionsByCrn(alternativesList), [alternativesList]);

  return (
    <div className={`planning-workspace ${compact ? 'planning-workspace-compact' : ''}`}>
      <section className="planning-card" aria-labelledby="course-selection-heading">
        <div className="planning-heading-row">
          <div>
            <h2 id="course-selection-heading">{headingPrefix}Real Course Catalog &amp; Section Search</h2>
            <p>Choose an actual catalog section before adding it to the shared planning schedule.</p>
          </div>
          <span className="planning-count">{courses.length || 0} courses</span>
        </div>

        {coursesError && <div className="planning-alert planning-alert-error">{coursesError}</div>}
        <label className="planning-label" htmlFor="course-select-dropdown">Course</label>
        <select
          id="course-select-dropdown"
          value={selectedCourseCode}
          onChange={(event) => onSelectCourse(event.target.value)}
          disabled={loadingCourses || courses.length === 0}
          className="planning-control"
        >
          <option value="">-- Choose a Course to View Sections --</option>
          {courses.map((course) => (
            <option key={course.COURSE} value={course.COURSE}>{course.COURSE} — {course.TITLE}</option>
          ))}
        </select>

        <div className="planning-quick-select" aria-label="Quick-select courses">
          <span>Quick select:</span>
          {QUICK_COURSES.map((code) => (
            <button
              key={code}
              type="button"
              id={`quick-select-${code.replace(/\s+/g, '-')}`}
              className={selectedCourseCode === code ? 'active' : ''}
              onClick={() => onSelectCourse(code)}
            >
              {code}
            </button>
          ))}
        </div>

        {selectedCourseCode && (
          <div className="section-results">
            <h3>Available Sections for {selectedCourseCode}</h3>
            {loadingSections && <p role="status">Loading sections from backend…</p>}
            {sectionsError && <div className="planning-alert planning-alert-error">{sectionsError}</div>}
            {!loadingSections && !sectionsError && availableGroups.length === 0 && <p>No active sections found for this course.</p>}
            {availableGroups.length > 0 && (
              <div className="section-list" aria-label={`Available sections for ${selectedCourseCode}`}>
                {availableGroups.map((records) => {
                  const section = records[0];
                  const crn = String(section.CRN);
                  const selected = selectedGroups.some((group) => String(group[0].CRN) === crn);
                  return (
                    <article className="section-option" key={crn}>
                      <div>
                        <strong>{section.COURSE} · Sec {section.SECT}</strong>
                        <span>CRN {crn} · {formatGroupedMeetingDisplay(records)}</span>
                        <span>{section.METHOD || 'In-Person'} · {section.CAMPUS || 'Campus TBA'} · {section.INSTRUCTOR || 'Instructor TBA'}</span>
                      </div>
                      <button type="button" onClick={() => onAddSectionGroup(records)} disabled={selected}>
                        {selected ? 'Selected' : '+ Add'}
                      </button>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="planning-card" aria-labelledby="schedule-heading">
        <div className="planning-heading-row">
          <div>
            <h2 id="schedule-heading">{headingPrefix}Proposed Schedule</h2>
            <p>{selectedGroups.length === 0 ? 'No sections selected yet.' : `${selectedGroups.length} section(s) selected and shared across Forms and Chatbot.`}</p>
          </div>
          {onShowDemoScheduleChange && (
            <label className="demo-toggle"><input type="checkbox" checked={showDemoSchedule} onChange={(event) => onShowDemoScheduleChange(event.target.checked)} /> Simulated demo data</label>
          )}
        </div>

        {!showDemoSchedule && selectedGroups.length > 0 && (
          <div className="selected-section-list" aria-label="Selected classes">
            {selectedGroups.map((group) => {
              const section = group[0];
              const crn = String(section.CRN);
              const conflict = conflictingIds.has(crn);
              return (
                <article className={`selected-section-card ${conflict ? 'conflict' : ''}`} key={crn}>
                  <div>
                    <strong>{section.COURSE} · Sec {section.SECT}</strong>
                    <span>CRN {crn}</span>
                    <span>{formatGroupedMeetingDisplay(group)}</span>
                  </div>
                  <div className="selected-section-actions">
                    {conflict && <span className="conflict-badge">Conflict</span>}
                    {onFindAlternatives && <button type="button" onClick={() => onFindAlternatives(section)}>Alternatives</button>}
                    <button type="button" className="danger" onClick={() => onRemoveSection(crn)}>Remove</button>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        <div className="calendar-scroll" aria-label="Weekly schedule calendar">
          <div className="weekly-calendar">
            <div className="calendar-header">Time</div>
            {DAYS.map((day) => <div className="calendar-header" key={day}>{day}</div>)}
            <div className="calendar-time-column">
              {hours.map((hour) => <div key={hour}>{hour}:00</div>)}
            </div>
            {DAYS.map((day) => (
              <div className="calendar-day" key={day}>
                {hours.map((hour) => <div className="calendar-hour" key={hour} />)}
                {displaySections.flatMap((section) => section.meetings.filter((meeting) => meeting.day === day).map((meeting, index) => {
                  const conflict = conflictingIds.has(section.id);
                  const conflictColumn = displaySections.findIndex((item) => item.id === section.id) % 2;
                  return (
                    <div
                      className={`calendar-event ${conflict ? 'conflict' : ''}`}
                      key={`${section.id}-${index}`}
                      style={{
                        ...calculateBlockStyle(meeting.startTime, meeting.endTime),
                        ...(conflict ? { left: conflictColumn === 0 ? '4%' : '52%', width: '44%' } : {}),
                      }}
                    >
                      <strong>{section.courseCode}</strong>
                      <span>{meeting.startTime}–{meeting.endTime}</span>
                      {conflict && <span>Conflict</span>}
                    </div>
                  );
                }))}
              </div>
            ))}
          </div>
        </div>

        {!showDemoSchedule && outsideGrid.length > 0 && (
          <div className="outside-schedule" aria-label="Sections outside the daytime calendar">
            <h3>Outside the Mon–Fri 8 AM–6 PM grid</h3>
            {outsideGrid.map((section) => (
              <article key={section.id}>
                <div><strong>{section.courseCode} · Sec {section.sect || 'TBA'}</strong><span>{section.scheduleNote}</span></div>
                <span className={`schedule-kind ${section.meetingCategory}`}>{section.meetingCategory === 'asynchronous' ? 'Asynchronous' : section.meetingCategory === 'unknown_tba' ? 'Time TBA' : 'Evening / weekend'}</span>
              </article>
            ))}
          </div>
        )}

        {alternativesTarget && onCloseAlternatives && onSwapAlternativeGroup && (
          <div className="alternatives-panel">
            <div className="planning-heading-row"><h3>Alternatives for {alternativesTarget.COURSE} · CRN {String(alternativesTarget.CRN)}</h3><button type="button" onClick={onCloseAlternatives}>Close</button></div>
            {loadingAlternatives && <p role="status">Searching backend alternatives…</p>}
            {alternativesError && <div className="planning-alert planning-alert-error">{alternativesError}</div>}
            {!loadingAlternatives && !alternativesError && alternativeGroups.length === 0 && <p>No non-conflicting open replacements were found.</p>}
            {alternativeGroups.map((group) => (
              <article className="section-option" key={String(group[0].CRN)}>
                <div><strong>Sec {group[0].SECT} · CRN {String(group[0].CRN)}</strong><span>{formatGroupedMeetingDisplay(group)}</span></div>
                <button type="button" onClick={() => onSwapAlternativeGroup(group)}>Use section</button>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
