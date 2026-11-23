import { describe, it } from 'node:test';
import assert from 'node:assert';
import type { ConversationRequest, ConversationResponse } from '../src/services/api';
import { mergeSessionEvidence, type SessionEvidenceRecord } from '../src/utils/sessionEvidence.ts';
import { missingContextLabel, pendingMessagesForRequest, quickPromptsForSelection, responseDetailLabel } from '../src/utils/conversationPresentation.ts';
import { CHAT_RETENTION_DAYS, MAX_SAVED_CONVERSATIONS, MAX_SAVED_MESSAGE_CHARACTERS, MAX_SAVED_MESSAGES, conversationTitle, historyFailureMessage, safeHistoryMetadata } from '../src/utils/conversationHistory.ts';

describe('Conversational Client Payload & State Handling', () => {
  it('correctly structures payload with full synthetic workload context', () => {
    const payload: ConversationRequest = {
      message: 'Can I take COP 4331 and MAP 3305 together?',
      student_id: 'Z24567901',
      recent_difficulty: 1,
      satisfied_with_performance: 'yes',
      work_hours: 5.0,
      preferred_max_credits: 15.0,
      recent_courses: ['CDA4240C', 'CDA4102', 'MAC2313'],
    };

    assert.strictEqual(payload.message, 'Can I take COP 4331 and MAP 3305 together?');
    assert.strictEqual(payload.student_id, 'Z24567901');
    assert.strictEqual(payload.work_hours, 5.0);
    assert.strictEqual(payload.satisfied_with_performance, 'yes');
    assert.strictEqual(payload.recent_courses?.length, 3);
  });

  it('correctly structures payload when workload context is omitted', () => {
    const payload: ConversationRequest = {
      message: 'Can I take COP 4331 and MAP 3305 together?',
      student_id: null,
      recent_difficulty: null,
      satisfied_with_performance: null,
      work_hours: null,
    };

    assert.strictEqual(payload.student_id, null);
    assert.strictEqual(payload.work_hours, null);
  });

  it('identifies engine_executed response state with completed assessment', () => {
    const mockResponse: ConversationResponse = {
      status: 'engine_executed',
      raw_message: 'Can I take COP 4331 and MAP 3305 together?',
      disposition: 'route_core_engine',
      target_handler: 'course_compatibility_engine',
      response_code: 'COMPATIBILITY_EVALUATION_COMPLETE',
      response_text: 'Workload compatibility evaluation completed for COP4331, MAP3305.',
      safe_to_route: true,
      missing_context: [],
      extracted_courses: ['COP4331', 'MAP3305'],
      engine_executed: true,
      engine_result: {
        assessment: 'Potentially manageable based on the information provided',
        proposed_credits: 6,
        recommendations: ['Recommended balance looks consistent.'],
      },
      disclaimer: 'SmartAdvisor conversational layer is a rule-based decision-support prototype.',
    };

    assert.strictEqual(mockResponse.status, 'engine_executed');
    assert.strictEqual(mockResponse.engine_executed, true);
    assert.strictEqual(mockResponse.extracted_courses.length, 2);
    assert.ok(mockResponse.engine_result?.assessment);
  });

  it('identifies clarification response state with missing context list', () => {
    const mockResponse: ConversationResponse = {
      status: 'clarification',
      raw_message: 'Can I take COP 4331 and MAP 3305 together?',
      disposition: 'route_core_engine',
      target_handler: 'course_compatibility_engine',
      response_code: 'MISSING_STUDENT_CONTEXT',
      response_text: 'Compatibility request recognized, but student context is required.',
      actionable_guidance: 'Please select a synthetic student profile.',
      safe_to_route: true,
      missing_context: ['student_id', 'work_hours'],
      extracted_courses: ['COP4331', 'MAP3305'],
      engine_executed: false,
      disclaimer: 'SmartAdvisor conversational layer is a rule-based decision-support prototype.',
    };

    assert.strictEqual(mockResponse.status, 'clarification');
    assert.strictEqual(mockResponse.engine_executed, false);
    assert.deepStrictEqual(mockResponse.missing_context, ['student_id', 'work_hours']);
  });

  it('identifies advisor escalation response without engine execution', () => {
    const mockResponse: ConversationResponse = {
      status: 'escalation',
      raw_message: 'Can you register me for COP 3530?',
      disposition: 'advisor_escalation',
      target_handler: 'academic_advisor',
      response_code: 'ADVISOR_ESCALATION_REQUIRED',
      response_text: 'An academic advisor or authorized office must make the official decision.',
      safe_to_route: false,
      missing_context: [],
      extracted_courses: ['COP3530'],
      engine_executed: false,
      disclaimer: 'SmartAdvisor conversational layer is a rule-based decision-support prototype.',
    };

    assert.strictEqual(mockResponse.status, 'escalation');
    assert.strictEqual(mockResponse.engine_executed, false);
    assert.strictEqual(mockResponse.safe_to_route, false);
  });

  it('identifies inactive informational RAG response without engine execution', () => {
    const mockResponse: ConversationResponse = {
      status: 'rag_inactive',
      raw_message: 'What topics are covered in COP 3530?',
      disposition: 'future_rag_candidate',
      target_handler: 'future_informational_rag',
      response_code: 'FUTURE_INFORMATIONAL_RAG_CANDIDATE',
      response_text: 'Source-grounded informational lookup is not enabled in the current prototype.',
      safe_to_route: false,
      missing_context: [],
      extracted_courses: ['COP3530'],
      engine_executed: false,
      disclaimer: 'SmartAdvisor conversational layer is a rule-based decision-support prototype.',
    };

    assert.strictEqual(mockResponse.status, 'rag_inactive');
    assert.strictEqual(mockResponse.engine_executed, false);
  });

  it('renders course-content routing metadata as student-facing language', () => {
    const response = {
      status: 'clarification', raw_message: 'What grading information is in the syllabus?',
      disposition: 'clarify', target_handler: 'future_informational_rag', response_code: 'SOURCE_SCOPE_INCOMPLETE',
      response_text: 'Please specify the term and section.', safe_to_route: false,
      missing_context: ['term_id', 'section'], extracted_courses: ['CAP4773'], engine_executed: false,
      disclaimer: 'Planning guidance.',
    } satisfies ConversationResponse;

    assert.strictEqual(responseDetailLabel(response), 'Course details needed');
    assert.deepStrictEqual(response.missing_context.map(missingContextLabel), ['term', 'section']);
  });

  it('builds suggestions from the actual planner selection', () => {
    const selected = [
      { course: 'CAP 4773', section: '001', crn: '18637', term: 202608 },
      { course: 'EGN 3343', section: '001', crn: '16828', term: 202608 },
    ];
    assert.deepStrictEqual(quickPromptsForSelection(selected), [
      'Do these classes conflict?',
      'Can I take CAP 4773 and EGN 3343 together?',
      'What topics are covered in CAP 4773?',
    ]);
    assert.match(quickPromptsForSelection([])[2], /\[COURSE\]/);
  });

  it('does not suggest source questions for an unmapped selected course', () => {
    const cap = [{ course: 'CAP 4773', section: '001', crn: '18637', term: 202608 }];
    const map = [{ course: 'MAP 3305', section: '003', crn: '16355', term: 202608 }];
    const sources = { CAP4773: ['course_description', 'syllabus'] };
    assert.deepStrictEqual(quickPromptsForSelection(cap, sources), [
      'What topics are covered in CAP 4773?',
      'What grading information is in the syllabus for CAP 4773?',
    ]);
    assert.deepStrictEqual(quickPromptsForSelection(map, sources), []);
  });

  it('describes pending work without claiming unconfirmed completion', () => {
    const messages = pendingMessagesForRequest('What grading information is in the syllabus?', 1);
    assert.match(messages[1], /Looking for approved information/);
    assert.doesNotMatch(messages.join(' '), /acquired|fetched|Gemini/);
  });

  it('stores only bounded display metadata for conversation history', () => {
    const response = {
      status: 'grounded_answer', raw_message: 'Question', disposition: 'future_rag_candidate',
      target_handler: 'future_informational_rag', response_code: 'RAG_ANSWERED', response_text: 'Answer',
      safe_to_route: true, missing_context: [], extracted_courses: ['CAP4773'], engine_executed: false,
      disclaimer: 'Verify with the official source.',
      citations: [{ title: 'CAP 4773 syllabus', url: 'https://example.edu/source', locator: 'heading:grading' }],
      acquired_evidence: [{ signature: 'must-not-persist', academic_sections: [{ text: 'raw source' }] }],
    } satisfies ConversationResponse;
    const metadata = safeHistoryMetadata(response, [{ course: 'CAP 4773', section: '001', crn: '18637', term: 202608 }]);
    const serialized = JSON.stringify(metadata);
    assert.equal(CHAT_RETENTION_DAYS, 30);
    assert.equal(MAX_SAVED_CONVERSATIONS, 10);
    assert.equal(MAX_SAVED_MESSAGES, 50);
    assert.equal(MAX_SAVED_MESSAGE_CHARACTERS, 4000);
    assert.equal(conversationTitle('  What   grading information is listed?  '), 'What grading information is listed?');
    assert.doesNotMatch(serialized, /signature|raw source|acquired_evidence/);
    assert.match(serialized, /CAP 4773 syllabus/);
  });

  it('reports safe history failures without exposing database details', () => {
    assert.equal(historyFailureMessage({ code: '42501', message: 'permission denied for table chat_messages' }, 'write'), 'Conversation history access is not enabled for this account yet.');
    assert.equal(historyFailureMessage({ code: 'PGRST205', details: 'schema cache' }, 'read'), 'Conversation history is not available in this deployment yet.');
    assert.doesNotMatch(historyFailureMessage(new Error('secret database detail'), 'write'), /secret|database detail/);
  });
});

describe('Session evidence bounds and identity', () => {
  const evidence = (id: string, category: 'syllabus' | 'course_description', section?: string): SessionEvidenceRecord => ({
    record_id: id, record_category: category, course_code: 'COP4331',
    section_scope: section ? { section } : undefined,
    session_provenance: { scheme: 'hmac-sha256-v1', signature: id },
  });

  it('keeps a syllabus when a course description arrives', () => {
    const syllabus = evidence('syllabus-002', 'syllabus', '002');
    const description = evidence('description', 'course_description');
    assert.deepStrictEqual(mergeSessionEvidence([syllabus], [description]).map((item) => item.record_id), ['description', 'syllabus-002']);
  });

  it('keeps distinct sections and caps the record count', () => {
    const records = Array.from({ length: 8 }, (_, index) => evidence(`syllabus-${index}`, 'syllabus', String(index)));
    const merged = mergeSessionEvidence([], records);
    assert.strictEqual(merged.length, 6);
    assert.strictEqual(merged[0].record_id, 'syllabus-0');
  });
});
