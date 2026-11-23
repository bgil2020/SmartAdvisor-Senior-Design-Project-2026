import type { ConversationResponse } from '../services/api';
import type { ConversationSectionContext } from './planningSelection';

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

function selectedCourses(sections: ConversationSectionContext[]): string[] {
  return [...new Set(sections.map((section) => section.course.trim()).filter(Boolean))];
}

export function quickPromptsForSelection(sections: ConversationSectionContext[]): string[] {
  const courses = selectedCourses(sections);
  if (courses.length === 0) {
    return [
      'Do [COURSE 1] and [COURSE 2] conflict?',
      'Can I take [COURSE 1] and [COURSE 2] together?',
      'What topics are covered in [COURSE]?',
    ];
  }
  if (courses.length === 1) {
    return [
      `What topics are covered in ${courses[0]}?`,
      `What grading information is in the syllabus for ${courses[0]}?`,
    ];
  }
  return [
    'Do these classes conflict?',
    `Can I take ${courses[0]} and ${courses[1]} together?`,
    `What topics are covered in ${courses[0]}?`,
  ];
}

export function pendingMessagesForRequest(question: string, selectionCount: number): string[] {
  const informational = /\b(syllabus|grading|grade|material|topics?|covered|learn|taught)\b/i.test(question);
  const schedule = /\b(conflict|schedule|section|together)\b/i.test(question);
  const middle = informational
    ? selectionCount > 0
      ? 'Looking for approved information for the selected course…'
      : 'Resolving the course and its approved information source…'
    : schedule
      ? 'Running the schedule check against the selected sections…'
      : 'Choosing the appropriate advising workflow…';
  return [
    selectionCount > 0 ? 'Checking your question and selected classes…' : 'Checking your question…',
    middle,
    'Validating the response and any supporting citations…',
    'Finishing your answer…',
  ];
}
