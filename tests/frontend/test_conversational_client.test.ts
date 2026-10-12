import { describe, it } from 'node:test';
import assert from 'node:assert';
import type { ConversationRequest, ConversationResponse } from '../../src/services/api';

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
});
