import { useState } from 'react'

function OnlineOverrideEvaluator() {
  const [courseCode, setCourseCode] = useState('')
  const [overrideCategory, setOverrideCategory] = useState('')
  const [overrideDescription, setOverrideDescription] = useState('')
  const [documentationStatus, setDocumentationStatus] = useState('')
  const [overrideResult, setOverrideResult] = useState(null)

  function handleOverrideEvaluation(event) {
    event.preventDefault()

    if (
      !courseCode.trim() ||
      !overrideCategory ||
      !overrideDescription.trim() ||
      !documentationStatus
    ) {
      setOverrideResult({
        status: 'More Information Needed',
        message: 'Please complete all fields before requesting a recommendation.'
      })
      return
    }

    const course = courseCode.trim().toUpperCase()
    const documentationAvailable = documentationStatus === 'available'

    let status = ''
    let message = ''

    if (overrideCategory === 'military') {
      status = documentationAvailable
        ? 'Advising Review Recommended'
        : 'Additional Documentation May Be Needed'

      message = documentationAvailable
        ? 'Active-duty military obligations may support an online override request. Include your supporting documentation when contacting advising staff.'
        : 'Active-duty military obligations may support an online override request. Contact advising staff to confirm what documentation is required.'
    } else if (overrideCategory === 'medical') {
      status = documentationAvailable
        ? 'Advising Review Recommended'
        : 'Additional Documentation May Be Needed'

      message = documentationAvailable
        ? 'Hospitalization or illness preventing in-person attendance may support an online override request. Supporting documentation should explain the attendance limitation.'
        : 'A medical circumstance may support an online override request. Contact advising staff to determine what supporting documentation is needed.'
    } else if (overrideCategory === 'transportation') {
      status = 'Individual Review Required'
      message =
        'Exceptional transportation circumstances may be considered individually and may require dean-level approval. Contact advising staff to discuss your situation and provide supporting information when available.'
    } else {
      status = 'Advising Consultation Recommended'
      message =
        'Your circumstances do not clearly match one of the categories represented in this prototype. Contact advising staff to discuss whether another option or exception is available.'
    }

    if (documentationStatus === 'unavailable') {
      message +=
        ' You indicated that supporting documentation is unavailable. Advising staff can help you find out if your request can be considered without it.'
    } else if (documentationStatus === 'not_yet') {
      message +=
        ' You indicated that supporting documentation has not yet been obtained. Ask advising staff what is required before submitting your formal request.'
    }

    setOverrideResult({
      status,
      course,
      message
    })
  }

  return (
    <section className="features">
      <h2>Online Course Override Evaluator</h2>

      <p>
        If circumstances prevent you from attending an in-person course,
        SmartAdvisor can provide preliminary guidance about whether your
        situation may qualify for advising review.
      </p>

      <form onSubmit={handleOverrideEvaluation} className="auth-form">
        <label htmlFor="overrideCourse">
          Course Requested Online
        </label>

        <input
          id="overrideCourse"
          type="text"
          value={courseCode}
          onChange={(event) => setCourseCode(event.target.value)}
          placeholder="Example: COP4610"
          required
        />

        <label htmlFor="overrideCategory">Circumstance</label>

        <select
          id="overrideCategory"
          value={overrideCategory}
          onChange={(event) => setOverrideCategory(event.target.value)}
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

        <label htmlFor="overrideDescription">
          Brief Description of Circumstances
        </label>

        <textarea
          id="overrideDescription"
          value={overrideDescription}
          onChange={(event) =>
            setOverrideDescription(event.target.value)
          }
          placeholder="Briefly explain why attending the course in person may not be possible."
          rows={4}
          required
        />

        <label htmlFor="overrideDocumentation">
          Supporting Documentation
        </label>

        <select
          id="overrideDocumentation"
          value={documentationStatus}
          onChange={(event) =>
            setDocumentationStatus(event.target.value)
          }
          required
        >
          <option value="">Select documentation status</option>
          <option value="available">
            Yes, documentation is available
          </option>
          <option value="not_yet">
            Not yet, but I may be able to obtain it
          </option>
          <option value="unavailable">
            No, documentation is currently unavailable
          </option>
        </select>

        <button type="submit">Get Recommendation</button>
      </form>

      {overrideResult && (
        <div className="override-result" role="status">
          <h3>SmartAdvisor Recommendation</h3>

          <p>
            <strong>Course:</strong> {overrideResult.course}
          </p>

          <p>
            <strong>Preliminary Status:</strong>{' '}
            {overrideResult.status}
          </p>

          <p>{overrideResult.message}</p>

          <p>
            <strong>Next Step:</strong> Contact FAU advising staff
            to discuss the request and confirm the official process.
          </p>
        </div>
      )}

      <p>
        <small>
          This is a rule-based prototype for preliminary academic
          planning guidance. It does not verify eligibility,
          check course availability, submit an override request,
          or grant approval. All official decisions remain with
          authorized university staff.
        </small>
      </p>
    </section>
  )
}

export default OnlineOverrideEvaluator