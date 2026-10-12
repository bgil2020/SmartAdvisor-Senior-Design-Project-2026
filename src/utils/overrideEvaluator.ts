export type OverrideResult = {
  status: string;
  course?: string;
  message: string;
};

export interface OverrideEvaluationInput {
  courseCode: string;
  overrideCategory: string;
  overrideDescription: string;
  documentationStatus: string;
}

export function evaluateOverride(input: OverrideEvaluationInput): OverrideResult {
  const { courseCode, overrideCategory, overrideDescription, documentationStatus } = input;

  if (
    !courseCode.trim() ||
    !overrideCategory ||
    !overrideDescription.trim() ||
    !documentationStatus
  ) {
    return {
      status: 'More Information Needed',
      message: 'Please complete all fields before requesting a recommendation.',
    };
  }

  const course = courseCode.trim().toUpperCase();
  const documentationAvailable = documentationStatus === 'available';

  let status: string;
  let message: string;

  if (overrideCategory === 'military') {
    status = documentationAvailable
      ? 'Advising Review Recommended'
      : 'Additional Documentation May Be Needed';

    message = documentationAvailable
      ? 'Active-duty military obligations may support an online override request. Include your supporting documentation when contacting advising staff.'
      : 'Active-duty military obligations may support an online override request. Contact advising staff to confirm what documentation is required.';
  } else if (overrideCategory === 'medical') {
    status = documentationAvailable
      ? 'Advising Review Recommended'
      : 'Additional Documentation May Be Needed';

    message = documentationAvailable
      ? 'Hospitalization or illness preventing in-person attendance may support an online override request. Supporting documentation should explain the attendance limitation.'
      : 'A medical circumstance may support an online override request. Contact advising staff to determine what supporting documentation is needed.';
  } else if (overrideCategory === 'transportation') {
    status = 'Individual Review Required';
    message =
      'Exceptional transportation circumstances may be considered individually and may require dean-level approval. Contact advising staff to discuss your situation and provide supporting information when available.';
  } else {
    status = 'Advising Consultation Recommended';
    message =
      'Your circumstances do not clearly match one of the categories represented in this prototype. Contact advising staff to discuss whether another option or exception is available.';
  }

  if (documentationStatus === 'unavailable') {
    message +=
      ' You indicated that supporting documentation is unavailable. Advising staff can help you find out if your request can be considered without it.';
  } else if (documentationStatus === 'not_yet') {
    message +=
      ' You indicated that supporting documentation has not yet been obtained. Ask advising staff what is required before submitting your formal request.';
  }

  return { status, course, message };
}
