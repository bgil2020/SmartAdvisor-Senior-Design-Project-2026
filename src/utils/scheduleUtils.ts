import type { RawSectionRecord } from '../services/api';

export type DayOfWeek = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI' | 'SAT' | 'SUN';

export interface MeetingTime {
  day: DayOfWeek;
  startTime: string; // 24h "HH:MM" format
  endTime: string;   // 24h "HH:MM" format
}

export type MeetingCategory = 'in_grid' | 'out_of_grid_timed' | 'asynchronous' | 'unknown_tba';

export interface CourseSection {
  id: string;
  courseCode: string;
  title: string;
  sect?: string;
  meetings: MeetingTime[];
  meetingCategory?: MeetingCategory;
  scheduleNote?: string;
  raw?: RawSectionRecord;
  rawRecords?: RawSectionRecord[];
}

export const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
export const START_HOUR = 8;  // 8:00 AM
export const END_HOUR = 18;   // 6:00 PM
export const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60; // 600 mins

export function parseTimeToMinutes(timeStr: string): number {
  const [hours, minutes] = timeStr.split(':').map(Number);
  return hours * 60 + minutes;
}

export function isValidTimeInterval(start24: string | null | undefined, end24: string | null | undefined): boolean {
  if (!start24 || !end24) return false;
  return parseTimeToMinutes(start24) < parseTimeToMinutes(end24);
}

export function getConflictingSectionIds(sections: CourseSection[]): Set<string> {
  const conflictingIds = new Set<string>();

  for (let i = 0; i < sections.length; i++) {
    for (let j = i + 1; j < sections.length; j++) {
      const secA = sections[i];
      const secB = sections[j];

      for (const mA of secA.meetings) {
        for (const mB of secB.meetings) {
          if (
            mA.day === mB.day &&
            mA.startTime < mB.endTime &&
            mB.startTime < mA.endTime
          ) {
            conflictingIds.add(secA.id);
            conflictingIds.add(secB.id);
          }
        }
      }
    }
  }

  return conflictingIds;
}

export function calculateBlockStyle(startTime: string, endTime: string) {
  const startMins = parseTimeToMinutes(startTime) - START_HOUR * 60;
  const durationMins = parseTimeToMinutes(endTime) - parseTimeToMinutes(startTime);

  const topPercent = (startMins / TOTAL_MINUTES) * 100;
  const heightPercent = (durationMins / TOTAL_MINUTES) * 100;

  return {
    top: `${topPercent}%`,
    height: `${heightPercent}%`,
  };
}

/**
 * Converts 12-hour AM/PM string (e.g., "04:00 PM", "9:30 AM") into 24-hour "HH:MM".
 * Validates minute bounds (00-59) and hour bounds (01-12).
 */
export function parse12HourTo24Hour(timeStr: string | null | undefined): string | null {
  if (!timeStr) return null;
  const clean = timeStr.trim().toUpperCase();
  const match = clean.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/);
  if (!match) return null;

  let hours = parseInt(match[1], 10);
  const minutesNum = parseInt(match[2], 10);
  const minutesStr = match[2];
  const period = match[3];

  if (hours < 1 || hours > 12) return null;
  if (minutesNum < 0 || minutesNum > 59) return null;

  if (period === 'PM' && hours !== 12) {
    hours += 12;
  } else if (period === 'AM' && hours === 12) {
    hours = 0;
  }

  return `${String(hours).padStart(2, '0')}:${minutesStr}`;
}

/**
 * Normalizes FAU single-letter day abbreviations (M, T, W, R, F, S, U) to DayOfWeek array.
 * Note: FAU uses R for Thursday, S for Saturday, U for Sunday.
 */
export function parseBackendDays(daysStr: string | null | undefined): DayOfWeek[] {
  if (!daysStr) return [];
  const clean = daysStr.trim().toUpperCase().replace(/[\s,]/g, '');
  const dayMapping: Record<string, DayOfWeek> = {
    M: 'MON',
    T: 'TUE',
    W: 'WED',
    R: 'THU',
    F: 'FRI',
    S: 'SAT',
    U: 'SUN',
  };

  const results: DayOfWeek[] = [];
  for (const char of clean) {
    const mapped = dayMapping[char];
    if (mapped && !results.includes(mapped)) {
      results.push(mapped);
    }
  }
  return results;
}

export interface MappedSectionResult {
  section: CourseSection;
  isUnscheduled: boolean;
  scheduleNote: string;
}

/**
 * Groups raw section records by CRN so distinct meeting rows belonging to the same section
 * are preserved and aggregated rather than discarded or treated as duplicates.
 */
export function groupRawSectionsByCrn(rawSections: RawSectionRecord[]): RawSectionRecord[][] {
  const map = new Map<string, RawSectionRecord[]>();
  for (const raw of rawSections) {
    const crnKey = String(raw.CRN ?? 'UNKNOWN').trim();
    const existing = map.get(crnKey);
    if (existing) {
      existing.push(raw);
    } else {
      map.set(crnKey, [raw]);
    }
  }
  return Array.from(map.values());
}

/**
 * Maps a group of raw records for a single CRN into a unified CourseSection.
 * Preserves all distinct timed meetings for conflict checking, including evening and weekend hours.
 */
export function mapGroupedSectionToCourseSection(records: RawSectionRecord[]): MappedSectionResult {
  if (!records || records.length === 0) {
    throw new Error('Cannot map empty records array to CourseSection');
  }

  const primary = records[0];
  const crnStr = String(primary.CRN ?? '0');
  const courseCode = String(primary.COURSE ?? 'UNKNOWN');
  const title = String(primary.TITLE ?? courseCode);
  const sect = primary.SECT ? String(primary.SECT) : undefined;

  const allMeetings: MeetingTime[] = [];
  const meetingSummaries: string[] = [];
  let isOnline = false;
  let hasValidTimedMeeting = false;

  for (const rec of records) {
    const method = String(rec.METHOD ?? '').toLowerCase();
    if (method.includes('online') || method.includes('distance') || method.includes('remote')) {
      isOnline = true;
    }

    const days = parseBackendDays(rec.DAYS);
    const start24 = parse12HourTo24Hour(rec['BEG TIME']);
    const end24 = parse12HourTo24Hour(rec['END TIME']);

    if (days.length > 0 && start24 && end24 && isValidTimeInterval(start24, end24)) {
      hasValidTimedMeeting = true;
      meetingSummaries.push(`${days.join('/')} ${rec['BEG TIME']} - ${rec['END TIME']}`);
      for (const day of days) {
        if (!allMeetings.some((m) => m.day === day && m.startTime === start24 && m.endTime === end24)) {
          allMeetings.push({ day, startTime: start24, endTime: end24 });
        }
      }
    }
  }

  const gridStartMins = START_HOUR * 60; // 480 (8:00 AM)
  const gridEndMins = END_HOUR * 60;     // 1080 (6:00 PM)

  if (!hasValidTimedMeeting) {
    const category: MeetingCategory = isOnline ? 'asynchronous' : 'unknown_tba';
    const note = isOnline
      ? 'Online / Distance Learning (Asynchronous - No fixed campus meeting)'
      : 'Schedule TBA (Meeting times not specified in schedule - cannot verify conflicts)';
    return {
      section: {
        id: crnStr,
        courseCode,
        title,
        sect,
        meetings: [],
        meetingCategory: category,
        scheduleNote: note,
        raw: primary,
        rawRecords: records,
      },
      isUnscheduled: true,
      scheduleNote: note,
    };
  }

  // Check if all meetings fit standard daytime grid (Mon-Fri, 8am-6pm)
  const standardDays: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
  const allFitInGrid = allMeetings.every((m) => {
    const sMins = parseTimeToMinutes(m.startTime);
    const eMins = parseTimeToMinutes(m.endTime);
    return standardDays.includes(m.day) && sMins >= gridStartMins && eMins <= gridEndMins;
  });

  const summaryText = meetingSummaries.join(', ');

  if (!allFitInGrid) {
    const note = `Evening / Weekend schedule (${summaryText}) — Conflict check active`;
    return {
      section: {
        id: crnStr,
        courseCode,
        title,
        sect,
        meetings: allMeetings,
        meetingCategory: 'out_of_grid_timed',
        scheduleNote: note,
        raw: primary,
        rawRecords: records,
      },
      isUnscheduled: true,
      scheduleNote: note,
    };
  }

  const note = summaryText;
  return {
    section: {
      id: crnStr,
      courseCode,
      title,
      sect,
      meetings: allMeetings,
      meetingCategory: 'in_grid',
      scheduleNote: note,
      raw: primary,
      rawRecords: records,
    },
    isUnscheduled: false,
    scheduleNote: note,
  };
}

/**
 * Convenience mapper for a single raw section record.
 */
export function mapBackendSectionToCourseSection(raw: RawSectionRecord): MappedSectionResult {
  return mapGroupedSectionToCourseSection([raw]);
}

export function formatMeetingDisplay(raw?: RawSectionRecord): string {
  if (!raw) return 'No schedule details';
  const days = raw.DAYS?.trim() || 'TBA';
  const beg = raw['BEG TIME']?.trim() || '';
  const end = raw['END TIME']?.trim() || '';
  const time = beg && end ? `${beg} - ${end}` : 'TBA';
  const method = raw.METHOD?.trim() || 'In-Person';
  return `${days} ${time} (${method})`;
}

export function formatGroupedMeetingDisplay(records?: RawSectionRecord[]): string {
  if (!records || records.length === 0) return 'No schedule details';
  const lines = records.map((r) => formatMeetingDisplay(r));
  return Array.from(new Set(lines)).join(' | ');
}