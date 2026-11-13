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