import { useState } from 'react';
import type { FormEvent } from 'react';

type OverrideResult = {
  status: string;
  course?: string;
  message: string;
};

export default function OnlineOverrideEvaluator() {
  const [courseCode, setCourseCode] = useState('');
  const [overrideCategory, setOverrideCategory] = useState('');
  const [overrideDescription, setOverrideDescription] = useState('');
  const [documentationStatus, setDocumentationStatus] = useState('');
  const [overrideResult, setOverrideResult] = useState<OverrideResult | null>(null);

  function handleOverrideEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (
      !courseCode.trim() ||
      !overrideCategory ||
      !overrideDescription.trim() ||
      !documentationStatus
    ) {
      setOverrideResult({
        status: 'More Information Needed',
        message: 'Please complete all fields before requesting a recommendation.',
      });
      return;
    }

    const course = courseCode.trim().toUpperCase();
    const documentationAvailable = documentationStatus === 'available';

    let status = '';
    let message = '';

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

    setOverrideResult({ status, course, message });
  }

  const fieldStyle = {
    width: '100%',
    padding: '0.5rem',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    boxSizing: 'border-box' as const,
  };

  return (
    <section
      style={{
        padding: '1.5rem',
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        maxWidth: '600px',
      }}
    >
      <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>
        Online Course Override Evaluator
      </h2>

      <p style={{ fontSize: '0.875rem', margin: '1rem 0' }}>
        SmartAdvisor provides preliminary guidance about circumstances
        that may support an online course override request.
      </p>

      <form
        onSubmit={handleOverrideEvaluation}
        style={{ display: 'grid', gap: '1rem' }}
      >
        <label>
          Course Requested Online
          <input
            type="text"
            value={courseCode}
            onChange={(event) => setCourseCode(event.target.value)}
            placeholder="Example: COP4610"
            style={fieldStyle}
            required
          />
        </label>

        <label>
          Circumstance
          <select
            value={overrideCategory}
            onChange={(event) => setOverrideCategory(event.target.value)}
            style={fieldStyle}
            required
          >
            <option value="">Select a circumstance</option>
            <option value="military">Active-Duty Military Obligation</option>
            <option value="medical">Hospitalization or Illness</option>
            <option value="transportation">
              Exceptional Transportation Circumstances
            </option>
            <option value="other">Other Circumstances</option>
          </select>
        </label>

        <label>
          Brief Description of Circumstances
          <textarea
            value={overrideDescription}
            onChange={(event) => setOverrideDescription(event.target.value)}
            placeholder="Explain why in-person attendance may not be possible."
            rows={4}
            style={fieldStyle}
            required
          />
        </label>

        <label>
          Supporting Documentation
          <select
            value={documentationStatus}
            onChange={(event) => setDocumentationStatus(event.target.value)}
            style={fieldStyle}
            required
          >
            <option value="">Select documentation status</option>
            <option value="available">Yes, documentation is available</option>
            <option value="not_yet">
              Not yet, but I may be able to obtain it
            </option>
            <option value="unavailable">
              No, documentation is currently unavailable
            </option>
          </select>
        </label>

        <button
          type="submit"
          style={{
            padding: '0.75rem',
            borderRadius: '4px',
            backgroundColor: '#2563eb',
            color: '#ffffff',
            border: 'none',
            fontWeight: 'bold',
            cursor: 'pointer',
          }}
        >
          Get Recommendation
        </button>
      </form>

      {overrideResult && (
        <div
          role="status"
          style={{
            marginTop: '1rem',
            padding: '1rem',
            backgroundColor: '#eff6ff',
            border: '1px solid #93c5fd',
            borderRadius: '6px',
          }}
        >
          <h3 style={{ fontWeight: 'bold' }}>
            SmartAdvisor Recommendation
          </h3>
          {overrideResult.course && (
            <p><strong>Course:</strong> {overrideResult.course}</p>
          )}
          <p><strong>Preliminary Status:</strong> {overrideResult.status}</p>
          <p>{overrideResult.message}</p>
          <p>
            <strong>Next Step:</strong> Contact FAU advising staff to
            discuss the request and confirm the official process.
          </p>
        </div>
      )}

      <p style={{ marginTop: '1rem', fontSize: '0.75rem', color: '#4b5563' }}>
        This is a rule-based prototype for preliminary academic planning.
        It does not verify eligibility, check course availability, submit
        an override request, or grant approval. All official decisions
        remain with authorized university staff.
      </p>
    </section>
  );
}