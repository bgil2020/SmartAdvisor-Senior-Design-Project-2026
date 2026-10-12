import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  parse12HourTo24Hour,
  parseBackendDays,
  mapBackendSectionToCourseSection,
  getConflictingSectionIds,
} from '../../src/utils/scheduleUtils.ts';
import type { RawSectionRecord } from '../../src/services/api.ts';

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
    });
  });

  describe('parseBackendDays', () => {
    it('parses single and multiple day codes', () => {
      assert.deepEqual(parseBackendDays('M'), ['MON']);
      assert.deepEqual(parseBackendDays('T  R'), ['TUE', 'THU']);
      assert.deepEqual(parseBackendDays('M  W  F'), ['MON', 'WED', 'FRI']);
      assert.deepEqual(parseBackendDays('M T W R F'), ['MON', 'TUE', 'WED', 'THU', 'FRI']);
    });

    it('handles empty, null, or unknown day codes', () => {
      assert.deepEqual(parseBackendDays(null), []);
      assert.deepEqual(parseBackendDays(''), []);
      assert.deepEqual(parseBackendDays('Online'), []);
    });
  });

  describe('mapBackendSectionToCourseSection', () => {
    it('maps an in-person, in-grid section to calendar meetings', () => {
      const raw: RawSectionRecord = {
        CRN: 19417,
        COURSE: 'CAP 4773',
        SECT: '001',
        TITLE: 'Intro Data Science Analytics',
        DAYS: 'T  R',
        'BEG TIME': '09:30 AM',
        'END TIME': '10:50 AM',
        METHOD: 'In-Person',
        'ENRL REMN': 20,
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, false);
      assert.equal(result.section.id, '19417');
      assert.equal(result.section.courseCode, 'CAP 4773');
      assert.equal(result.section.meetings.length, 2);
      assert.equal(result.section.meetings[0].day, 'TUE');
      assert.equal(result.section.meetings[0].startTime, '09:30');
      assert.equal(result.section.meetings[0].endTime, '10:50');
      assert.equal(result.section.meetings[1].day, 'THU');
    });

    it('marks online sections with missing times as unscheduled', () => {
      const raw: RawSectionRecord = {
        CRN: 20142,
        COURSE: 'COP 3530',
        SECT: '003',
        TITLE: 'Data Structures',
        DAYS: null,
        'BEG TIME': null,
        'END TIME': null,
        METHOD: 'Online',
        'ENRL REMN': 5,
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, true);
      assert.match(result.scheduleNote, /Online/);
      assert.equal(result.section.meetings.length, 0);
    });

    it('marks evening sections outside 8am-6pm as extended unscheduled', () => {
      const raw: RawSectionRecord = {
        CRN: 18637,
        COURSE: 'CAP 4773',
        SECT: '001',
        TITLE: 'Intro Data Science Analytics',
        DAYS: 'T',
        'BEG TIME': '04:00 PM',
        'END TIME': '06:50 PM', // ends after 18:00
        METHOD: 'In-Person',
        'ENRL REMN': 26,
      };

      const result = mapBackendSectionToCourseSection(raw);
      assert.equal(result.isUnscheduled, true);
      assert.match(result.scheduleNote, /Evening/);
    });
  });

  describe('Real Section Conflict Detection', () => {
    it('detects overlap between two scheduled real sections on Tuesday', () => {
      const secA = mapBackendSectionToCourseSection({
        CRN: 10001,
        COURSE: 'COP 3530',
        SECT: '001',
        TITLE: 'Data Structures',
        DAYS: 'T  R',
        'BEG TIME': '09:30 AM',
        'END TIME': '10:50 AM',
      }).section;

      const secB = mapBackendSectionToCourseSection({
        CRN: 10002,
        COURSE: 'MAC 2312',
        SECT: '002',
        TITLE: 'Calculus II',
        DAYS: 'T  R',
        'BEG TIME': '10:00 AM', // overlaps 09:30 - 10:50
        'END TIME': '11:20 AM',
      }).section;

      const conflicting = getConflictingSectionIds([secA, secB]);
      assert.equal(conflicting.has('10001'), true);
      assert.equal(conflicting.has('10002'), true);
    });
  });
});
