import type { RawSectionRecord } from '../services/api';

export type DayOfWeek = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI';

export interface MeetingTime {
  day: DayOfWeek;
  startTime: string; // 24h "HH:MM" format
  endTime: string;   // 24h "HH:MM" format
}

export interface CourseSection {
  id: string;
  courseCode: string;
  title: string;
  meetings: MeetingTime[];
  raw?: RawSectionRecord;
}

export const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
export const START_HOUR = 8;  // 8:00 AM
export const END_HOUR = 18;   // 6:00 PM
export const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60; // 600 mins

export function parseTimeToMinutes(timeStr: string): number {
  const [hours, minutes] = timeStr.split(':').map(Number);
  return hours * 60 + minutes;
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
 */
export function parse12HourTo24Hour(timeStr: string | null | undefined): string | null {
  if (!timeStr) return null;
  const clean = timeStr.trim().toUpperCase();
  const match = clean.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/);
  if (!match) return null;

  let hours = parseInt(match[1], 10);
  const minutes = match[2];
  const period = match[3];

  if (hours < 1 || hours > 12) return null;

  if (period === 'PM' && hours !== 12) {
    hours += 12;
  } else if (period === 'AM' && hours === 12) {
    hours = 0;
  }

  return `${String(hours).padStart(2, '0')}:${minutes}`;
}

/**
 * Normalizes FAU single-letter day abbreviations (M, T, W, R, F) to DayOfWeek array.
 * Note: FAU uses R for Thursday.
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
 * Maps raw backend FAU section records to calendar course section structures.
 * Distinguishes in-grid daytime meetings from asynchronous, online, or evening meetings.
 */
export function mapBackendSectionToCourseSection(raw: RawSectionRecord): MappedSectionResult {
  const crnStr = String(raw.CRN ?? '0');
  const courseCode = String(raw.COURSE ?? 'UNKNOWN');
  const title = String(raw.TITLE ?? courseCode);

  const days = parseBackendDays(raw.DAYS);
  const start24 = parse12HourTo24Hour(raw['BEG TIME']);
  const end24 = parse12HourTo24Hour(raw['END TIME']);

  const method = String(raw.METHOD ?? '').toLowerCase();
  const isOnline = method.includes('online') || method.includes('distance') || method.includes('remote');

  // Check if meetings fit within 8:00 AM (08:00) to 6:00 PM (18:00) calendar range
  if (!start24 || !end24 || days.length === 0) {
    const note = isOnline
      ? 'Online / Distance Learning (No fixed campus meeting)'
      : 'TBA / Meeting times not specified in schedule';
    return {
      section: { id: crnStr, courseCode, title, meetings: [], raw },
      isUnscheduled: true,
      scheduleNote: note,
    };
  }

  const startMins = parseTimeToMinutes(start24);
  const endMins = parseTimeToMinutes(end24);
  const gridStartMins = START_HOUR * 60; // 480
  const gridEndMins = END_HOUR * 60;     // 1080

  if (startMins < gridStartMins || endMins > gridEndMins) {
    const timeDisplay = `${raw['BEG TIME']} - ${raw['END TIME']}`;
    return {
      section: { id: crnStr, courseCode, title, meetings: [], raw },
      isUnscheduled: true,
      scheduleNote: `Evening / Extended schedule (${days.join(', ')} ${timeDisplay})`,
    };
  }

  const meetings: MeetingTime[] = days.map((day) => ({
    day,
    startTime: start24,
    endTime: end24,
  }));

  return {
    section: { id: crnStr, courseCode, title, meetings, raw },
    isUnscheduled: false,
    scheduleNote: `${days.join(', ')} ${raw['BEG TIME']} - ${raw['END TIME']}`,
  };
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