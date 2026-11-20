import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import type { RawSectionRecord } from '../src/services/api.ts';
import { appendTranscriptEntry, isCurrentConversationEpoch } from '../src/utils/conversationState.ts';
import { addSelectedSectionGroup, commonSelectedTerm, describeSelectedSections, removeSelectedSection, toConversationSections } from '../src/utils/planningSelection.ts';
import { mapGroupedSectionToCourseSection } from '../src/utils/scheduleUtils.ts';

const row = (overrides: Partial<RawSectionRecord>): RawSectionRecord => ({
  CRN: 12345, COURSE: 'COP 4331', SECT: '002', TITLE: 'Object-Oriented Design', TERM: 202608,
  DAYS: 'MW', 'BEG TIME': '09:00 AM', 'END TIME': '10:20 AM', ...overrides,
});

describe('shared planning selection', () => {
  it('adds all meetings for a section once and removes them together', () => {
    const group = [row({ DAYS: 'M' }), row({ DAYS: 'W' })];
    const selected = addSelectedSectionGroup([], group);
    assert.equal(selected.length, 2);
    assert.strictEqual(addSelectedSectionGroup(selected, group), selected);
    assert.deepEqual(removeSelectedSection(selected, 12345), []);
  });

  it('creates exact structured conversation context from the shared model', () => {
    const context = toConversationSections([row({}), row({ CRN: 23456, COURSE: 'MAP 3305', SECT: '001' })]);
    assert.deepEqual(context.map(({ crn, course, section }) => ({ crn, course, section })), [
      { crn: '12345', course: 'COP 4331', section: '002' },
      { crn: '23456', course: 'MAP 3305', section: '001' },
    ]);
    assert.equal(commonSelectedTerm(context), 202608);
    assert.match(describeSelectedSections(context), /CRN 12345/);
  });

  it('preserves multiple meetings and labels asynchronous and missing schedules truthfully', () => {
    const timed = mapGroupedSectionToCourseSection([row({ DAYS: 'M' }), row({ DAYS: 'W' })]).section;
    assert.deepEqual(timed.meetings.map((meeting) => meeting.day), ['MON', 'WED']);
    assert.equal(mapGroupedSectionToCourseSection([row({ METHOD: 'Online', DAYS: null, 'BEG TIME': null, 'END TIME': null })]).section.meetingCategory, 'asynchronous');
    assert.equal(mapGroupedSectionToCourseSection([row({ METHOD: 'In Person', DAYS: null, 'BEG TIME': null, 'END TIME': null })]).section.meetingCategory, 'unknown_tba');
  });
});

describe('conversation transcript safeguards', () => {
  it('accumulates messages without mutating previous entries', () => {
    const first = appendTranscriptEntry<string>([], 'student');
    const second = appendTranscriptEntry(first, 'assistant');
    assert.deepEqual(first, ['student']);
    assert.deepEqual(second, ['student', 'assistant']);
  });

  it('rejects responses from an epoch invalidated by clear chat', () => {
    assert.equal(isCurrentConversationEpoch(4, 4), true);
    assert.equal(isCurrentConversationEpoch(4, 5), false);
  });
});
