import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { evaluateOverride } from '../../src/utils/overrideEvaluator.ts';
import {
  parseTimeToMinutes,
  getConflictingSectionIds,
  calculateBlockStyle,
} from '../../src/utils/scheduleUtils.ts';
import { MOCK_SECTIONS } from '../../src/types/schedule.ts';

describe('Online Override Evaluator Logic', () => {
  it('returns "More Information Needed" when required fields are empty', () => {
    const resultEmptyCourse = evaluateOverride({
      courseCode: '   ',
      overrideCategory: 'military',
      overrideDescription: 'Active duty deployment',
      documentationStatus: 'available',
    });
    assert.equal(resultEmptyCourse.status, 'More Information Needed');
    assert.match(resultEmptyCourse.message, /Please complete all fields/);

    const resultMissingCategory = evaluateOverride({
      courseCode: 'COP4610',
      overrideCategory: '',
      overrideDescription: 'Active duty deployment',
      documentationStatus: 'available',
    });
    assert.equal(resultMissingCategory.status, 'More Information Needed');

    const resultMissingDesc = evaluateOverride({
      courseCode: 'COP4610',
      overrideCategory: 'military',
      overrideDescription: '   ',
      documentationStatus: 'available',
    });
    assert.equal(resultMissingDesc.status, 'More Information Needed');

    const resultMissingDocs = evaluateOverride({
      courseCode: 'COP4610',
      overrideCategory: 'military',
      overrideDescription: 'Active duty deployment',
      documentationStatus: '',
    });
    assert.equal(resultMissingDocs.status, 'More Information Needed');
  });

  it('evaluates military circumstance with documentation available', () => {
    const result = evaluateOverride({
      courseCode: '  cop4610  ',
      overrideCategory: 'military',
      overrideDescription: 'Active duty deployment orders received.',
      documentationStatus: 'available',
    });

    assert.equal(result.status, 'Advising Review Recommended');
    assert.equal(result.course, 'COP4610');
    assert.match(result.message, /Active-duty military obligations may support/);
    assert.match(result.message, /Include your supporting documentation/);
  });

  it('evaluates military circumstance with documentation unavailable', () => {
    const result = evaluateOverride({
      courseCode: 'COP4610',
      overrideCategory: 'military',
      overrideDescription: 'Orders pending release.',
      documentationStatus: 'unavailable',
    });

    assert.equal(result.status, 'Additional Documentation May Be Needed');
    assert.match(result.message, /Active-duty military obligations/);
    assert.match(result.message, /supporting documentation is unavailable/);
  });

  it('evaluates military circumstance with documentation not yet obtained', () => {
    const result = evaluateOverride({
      courseCode: 'COP4610',
      overrideCategory: 'military',
      overrideDescription: 'Awaiting commanding officer letter.',
      documentationStatus: 'not_yet',
    });

    assert.equal(result.status, 'Additional Documentation May Be Needed');
    assert.match(result.message, /documentation has not yet been obtained/);
  });

  it('evaluates medical circumstance with documentation available', () => {
    const result = evaluateOverride({
      courseCode: 'CAP4773',
      overrideCategory: 'medical',
      overrideDescription: 'Hospitalization and mobility restrictions.',
      documentationStatus: 'available',
    });

    assert.equal(result.status, 'Advising Review Recommended');
    assert.equal(result.course, 'CAP4773');
    assert.match(result.message, /Hospitalization or illness preventing in-person attendance/);
    assert.match(result.message, /explain the attendance limitation/);
  });

  it('evaluates medical circumstance with documentation unavailable', () => {
    const result = evaluateOverride({
      courseCode: 'CAP4773',
      overrideCategory: 'medical',
      overrideDescription: 'Medical condition flare-up.',
      documentationStatus: 'unavailable',
    });

    assert.equal(result.status, 'Additional Documentation May Be Needed');
    assert.match(result.message, /supporting documentation is unavailable/);
  });

  it('evaluates transportation circumstance with dean-level referral', () => {
    const result = evaluateOverride({
      courseCode: 'COP4331',
      overrideCategory: 'transportation',
      overrideDescription: 'Extreme transit disruption preventing commute.',
      documentationStatus: 'available',
    });

    assert.equal(result.status, 'Individual Review Required');
    assert.equal(result.course, 'COP4331');
    assert.match(result.message, /dean-level approval/);
  });

  it('evaluates other circumstance with advising consultation recommendation', () => {
    const result = evaluateOverride({
      courseCode: 'CEN4214',
      overrideCategory: 'other',
      overrideDescription: 'Unique work scheduling conflict with required core.',
      documentationStatus: 'not_yet',
    });

    assert.equal(result.status, 'Advising Consultation Recommended');
    assert.match(result.message, /do not clearly match one of the categories/);
    assert.match(result.message, /documentation has not yet been obtained/);
  });
});

describe('Schedule Calendar Utilities', () => {
  it('correctly converts time strings to minutes', () => {
    assert.equal(parseTimeToMinutes('08:00'), 480);
    assert.equal(parseTimeToMinutes('09:30'), 570);
    assert.equal(parseTimeToMinutes('18:00'), 1080);
  });

  it('identifies conflicting section IDs in demo schedule', () => {
    const conflictingIds = getConflictingSectionIds(MOCK_SECTIONS);
    assert.equal(conflictingIds.has('sec-1'), true);
    assert.equal(conflictingIds.has('sec-2'), true);
  });

  it('calculates position block styles accurately', () => {
    const style = calculateBlockStyle('09:00', '10:30');
    assert.equal(typeof style.top, 'string');
    assert.equal(typeof style.height, 'string');
    assert.ok(style.top.endsWith('%'));
    assert.ok(style.height.endsWith('%'));
  });
});
