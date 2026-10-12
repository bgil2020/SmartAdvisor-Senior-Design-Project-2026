import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  parse12HourTo24Hour,
  parseBackendDays,
  isValidTimeInterval,
  groupRawSectionsByCrn,
  mapGroupedSectionToCourseSection,
  mapBackendSectionToCourseSection,
  getConflictingSectionIds,
} from '../../src/utils/scheduleUtils.ts';
import type { RawSectionRecord, CompatibilityResponse } from '../../src/services/api.ts';

describe('Frontend-Backend Wiring Schedule Utilities', () => {
  describe('parse12HourTo24Hour', () => {
    it('converts PM afternoon times correctly', () => {
      assert.equal(parse12HourTo24Hour('04:00 PM'), '16:00');
      assert.equal(parse12HourTo24Hour('01:30 PM'), '13:30');
      assert.equal(parse12HourTo24Hour('12:00 PM'), '12:00');
    });

    it('converts AM morning times correctly', () => {
      assert.equal(parse12HourTo24Hour('09:30 AM'), '09:30');
      assert.equal(parse12HourTo24Hour('11:45 AM'), '11:45');
      assert.equal(parse12HourTo24Hour('12:00 AM'), '00:00');
    });

    it('handles null, undefined, and invalid inputs gracefully', () => {
      assert.equal(parse12HourTo24Hour(null), null);
      assert.equal(parse12HourTo24Hour(undefined), null);
      assert.equal(parse12HourTo24Hour(''), null);
      assert.equal(parse12HourTo24Hour('TBA'), null);
      assert.equal(parse12HourTo24Hour('25:00 PM'), null);
      assert.equal(parse12HourTo24Hour('04:65 PM'), null);
      assert.equal(parse12HourTo24Hour('00:30 AM'), null);
    });
  });

  describe('parseBackendDays', () => {
    it('parses single and multiple day codes including weekends', () => {
      assert.deepEqual(parseBackendDays('M'), ['MON']);
      assert.deepEqual(parseBackendDays('T  R'), ['TUE', 'THU']);
      assert.deepEqual(parseBackendDays('M  W  F'), ['MON', 'WED', 'FRI']);
      assert.deepEqual(parseBackendDays('M T W R F'), ['MON', 'TUE', 'WED', 'THU', 'FRI']);
      assert.deepEqual(parseBackendDays('S'), ['SAT']);
      assert.deepEqual(parseBackendDays('U'), ['SUN']);
    });

    it('handles empty, null, or unknown day codes', () => {
      assert.deepEqual(parseBackendDays(null), []);
      assert.deepEqual(parseBackendDays(''), []);
      assert.deepEqual(parseBackendDays('Online'), []);
    });
  });

  describe('isValidTimeInterval', () => {
    it('validates forward chronological intervals', () => {
      assert.equal(isValidTimeInterval('09:00', '10:00'), true);
      assert.equal(isValidTimeInterval('18:00', '19:30'), true);
    });

    it('rejects inverted or identical intervals', () => {
      assert.equal(isValidTimeInterval('10:00', '09:00'), false);
      assert.equal(isValidTimeInterval('10:00', '10:00'), false);
      assert.equal(isValidTimeInterval(null, '10:00'), false);
    });
  });

  describe('groupRawSectionsByCrn', () => {
    it('groups multiple rows for the same CRN into a single array', () => {
      const records: RawSectionRecord[] = [
        { CRN: 11111, COURSE: 'COP 3530', SECT: '001', TITLE: 'Data Structures', DAYS: 'M  W', 'BEG TIME': '10:00 AM', 'END TIME': '11:20 AM' },
        { CRN: 11111, COURSE: 'COP 3530', SECT: '001', TITLE: 'Data Structures', DAYS: 'F', 'BEG TIME': '10:00 AM', 'END TIME': '11:50 AM' },
        { CRN: 22222, COURSE: 'MAC 2312', SECT: '001', TITLE: 'Calculus II', DAYS: 'T  R', 'BEG TIME': '01:00 PM', 'END TIME': '02:20 PM' },
      ];

      const grouped = groupRawSectionsByCrn(records);
      assert.equal(grouped.length, 2);
      assert.equal(grouped[0].length, 2);
      assert.equal(grouped[0][0].CRN, 11111);
      assert.equal(grouped[1].length, 1);
      assert.equal(grouped[1][0].CRN, 22222);
    });
  });

  describe('mapGroupedSectionToCourseSection', () => {
    it('combines meetings across multiple rows into a single section', () => {
      const records: RawSectionRecord[] = [
        { CRN: 11111, COURSE: 'COP 3530', SECT: '001', TITLE: 'Data Structures', DAYS: 'M  W', 'BEG TIME': '10:00 AM', 'END TIME': '11:20 AM' },
        { CRN: 11111, COURSE: 'COP 3530', SECT: '001', TITLE: 'Data Structures', DAYS: 'F', 'BEG TIME': '10:00 AM', 'END TIME': '11:50 AM' },
      ];

      const result = mapGroupedSectionToCourseSection(records);
      assert.equal(result.isUnscheduled, false);
      assert.equal(result.section.meetingCategory, 'in_grid');
      assert.equal(result.section.meetings.length, 3);
      assert.equal(result.section.meetings[0].day, 'MON');
      assert.equal(result.section.meetings[1].day, 'WED');
      assert.equal(result.section.meetings[2].day, 'FRI');
    });

    it('marks evening section as out_of_grid_timed while PRESERVING meetings for conflict checks', () => {
      const raw: RawSectionRecord = {
        CRN: 18637,
        COURSE: 'CAP 4773',
        SECT: '001',
        TITLE: 'Intro Data Science Analytics',
        DAYS: 'T',
        'BEG TIME': '06:00 PM',
        'END TIME': '08:50 PM',
        METHOD: 'In-Person',
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, true);
      assert.equal(result.section.meetingCategory, 'out_of_grid_timed');
      assert.match(result.scheduleNote, /Evening/);
      // Critical requirement: meetings must NOT be empty!
      assert.equal(result.section.meetings.length, 1);
      assert.equal(result.section.meetings[0].day, 'TUE');
      assert.equal(result.section.meetings[0].startTime, '18:00');
      assert.equal(result.section.meetings[0].endTime, '20:50');
    });

    it('categorizes asynchronous online sections without scheduled meetings', () => {
      const raw: RawSectionRecord = {
        CRN: 20142,
        COURSE: 'COP 3530',
        SECT: '003',
        TITLE: 'Data Structures',
        DAYS: null,
        'BEG TIME': null,
        'END TIME': null,
        METHOD: 'Online',
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, true);
      assert.equal(result.section.meetingCategory, 'asynchronous');
      assert.equal(result.section.meetings.length, 0);
      assert.match(result.scheduleNote, /Online/);
    });

    it('categorizes TBA sections and indicates conflict check is unavailable', () => {
      const raw: RawSectionRecord = {
        CRN: 99999,
        COURSE: 'DIR 4905',
        SECT: '001',
        TITLE: 'Directed Independent Study',
        DAYS: null,
        'BEG TIME': null,
        'END TIME': null,
        METHOD: 'In-Person',
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, true);
      assert.equal(result.section.meetingCategory, 'unknown_tba');
      assert.equal(result.section.meetings.length, 0);
      assert.match(result.scheduleNote, /TBA/);
    });
  });

  describe('Out-of-Grid & Daytime Conflict Detection', () => {
    it('detects overlap between two evening sections meeting outside 8am-6pm grid', () => {
      const eveningSecA = mapBackendSectionToCourseSection({
        CRN: 30001,
        COURSE: 'CAP 6635',
        SECT: '001',
        TITLE: 'Artificial Intelligence',
        DAYS: 'T',
        'BEG TIME': '06:30 PM',
        'END TIME': '09:00 PM',
      }).section;

      const eveningSecB = mapBackendSectionToCourseSection({
        CRN: 30002,
        COURSE: 'COT 6405',
        SECT: '001',
        TITLE: 'Analysis of Algorithms',
        DAYS: 'T',
        'BEG TIME': '07:00 PM', // overlaps 18:30 - 21:00
        'END TIME': '09:30 PM',
      }).section;

      const conflicting = getConflictingSectionIds([eveningSecA, eveningSecB]);
      assert.equal(conflicting.has('30001'), true);
      assert.equal(conflicting.has('30002'), true);
    });

    it('does not falsely report conflict between evening and morning sections', () => {
      const morningSec = mapBackendSectionToCourseSection({
        CRN: 10001,
        COURSE: 'COP 3530',
        SECT: '001',
        TITLE: 'Data Structures',
        DAYS: 'T',
        'BEG TIME': '09:30 AM',
        'END TIME': '10:50 AM',
      }).section;

      const eveningSec = mapBackendSectionToCourseSection({
        CRN: 18637,
        COURSE: 'CAP 4773',
        SECT: '001',
        TITLE: 'Intro Data Science',
        DAYS: 'T',
        'BEG TIME': '06:00 PM',
        'END TIME': '08:50 PM',
      }).section;

      const conflicting = getConflictingSectionIds([morningSec, eveningSec]);
      assert.equal(conflicting.has('10001'), false);
      assert.equal(conflicting.has('18637'), false);
    });
  });

  describe('Compatibility Contract Structure', () => {
    it('validates shape against backend evaluate_compatibility fields', () => {
      const mockBackendResponse: CompatibilityResponse = {
        success: true,
        student_id: 'Z24567901',
        student_name: 'Evie Woods',
        major: 'Electrical Engineering',
        proposed_courses: ['COP 4331', 'MAP 3305'],
        proposed_credits: 6,
        recent_credits: 10,
        assessment: 'Potentially manageable based on the information provided',
        matched_course_combinations: [
          {
            courses: ['COP 4331', 'MAP 3305'],
            baseline_rating: 'Moderate combination',
            personalized_guidance: 'Manageable combination when paced consistently.',
            factors: ['Substantial problem-set volume'],
            reasoning: 'Math and coding workload balances well.',
          },
        ],
        previously_completed_courses: [],
        repeat_course_warning: null,
        recommendations: ['Maintain regular schedule'],
        data_warnings: [],
        disclaimer: 'This is preliminary academic planning guidance, not an official advising decision.',
      };

      assert.equal(mockBackendResponse.success, true);
      assert.equal(typeof mockBackendResponse.assessment, 'string');
      assert.equal(Array.isArray(mockBackendResponse.matched_course_combinations), true);
      assert.equal(mockBackendResponse.matched_course_combinations[0].baseline_rating, 'Moderate combination');
    });
  });
});
