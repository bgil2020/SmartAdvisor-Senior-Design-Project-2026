import type { DayOfWeek, MeetingTime, CourseSection } from '../utils/scheduleUtils';

export type { DayOfWeek, MeetingTime, CourseSection };

export const MOCK_SECTIONS: CourseSection[] = [
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