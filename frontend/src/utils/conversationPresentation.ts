import type { ConversationResponse } from '../services/api';

export function responseDetailLabel(response: ConversationResponse): string {
  if (response.response_code === 'SOURCE_SCOPE_INCOMPLETE' || response.response_code === 'SOURCE_SCOPE_AMBIGUOUS') {
    return 'Course details needed';
  }
  const labels: Record<string, string> = {
    future_informational_rag: 'Course content lookup',
    scheduling_engine: 'Schedule check',
    course_compatibility_engine: 'Course workload check',
    online_override_eligibility_engine: 'Online-course screening',
    academic_advisor: 'Advisor assistance',
  };
  return labels[response.target_handler] ?? 'SmartAdvisor response';
}

export function missingContextLabel(value: string): string {
  return ({ course_code: 'course', term_id: 'term', section: 'section' } as Record<string, string>)[value] ?? value.replaceAll('_', ' ');
}
