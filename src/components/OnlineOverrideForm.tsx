import React, { useState } from 'react';
import { OverrideFormState } from '../types/override';

export const OnlineOverrideForm: React.FC = () => {
  const [form, setForm] = useState<OverrideFormState>({
    courseCode: '',
    reasonCategory: '',
    justification: '',
    attachedFile: null,
    isSubmitting: false,
    status: 'IDLE',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setForm((prev) => ({ ...prev, isSubmitting: true }));

    setTimeout(() => {
      setForm((prev) => ({ ...prev, isSubmitting: false, status: 'SUCCESS' }));
    }, 1000);
  };

  if (form.status === 'SUCCESS') {
    return (
      <div className="p-6 bg-green-50 border border-green-300 text-green-800 rounded-lg max-w-xl">
        <h3 className="text-lg font-bold mb-2">Override Request Submitted</h3>
        <p className="text-sm">
          Your online override request for <strong>{form.courseCode}</strong> has been submitted.
        </p>
        <button
          onClick={() => setForm({ courseCode: '', reasonCategory: '', justification: '', attachedFile: null, isSubmitting: false, status: 'IDLE' })}
          className="mt-4 px-4 py-2 bg-green-700 text-white rounded text-xs font-semibold"
        >
          Submit Another Request
        </button>
      </div>
    );
  }

  const isFormValid =
    form.courseCode.trim().length > 0 &&
    form.reasonCategory !== '' &&
    form.justification.trim().length >= 30;

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl p-6 bg-white border rounded-lg shadow-sm space-y-4">
      <h2 className="text-xl font-bold border-b pb-2">Online-Course Override Questionnaire</h2>

      <div>
        <label className="block text-xs font-semibold mb-1">Course Code</label>
        <input
          type="text"
          placeholder="e.g., CS 101"
          value={form.courseCode}
          onChange={(e) => setForm({ ...form, courseCode: e.target.value })}
          className="w-full p-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
      </div>

      <div>
        <label className="block text-xs font-semibold mb-1">Reason Category</label>
        <select
          value={form.reasonCategory}
          onChange={(e) => setForm({ ...form, reasonCategory: e.target.value as any })}
          className="w-full p-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option value="">-- Select Category --</option>
          <option value="SCHEDULE_CONFLICT">Schedule Conflict</option>
          <option value="DEGREE_REQUIREMENT">Degree Requirement</option>
          <option value="PREREQ_WAIVER">Prerequisite Waiver</option>
          <option value="OTHER">Other</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-semibold mb-1">Justification (Min 30 Characters)</label>
        <textarea
          rows={4}
          placeholder="Provide rationale for override..."
          value={form.justification}
          onChange={(e) => setForm({ ...form, justification: e.target.value })}
          className="w-full p-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        <div className="text-[11px] text-gray-400 mt-1">
          {form.justification.length} / 30 minimum characters
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold mb-1">Attachment (Optional)</label>
        <input
          type="file"
          onChange={(e) => setForm({ ...form, attachedFile: e.target.files?.[0] || null })}
          className="w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-gray-100"
        />
      </div>

      <button
        type="submit"
        disabled={!isFormValid || form.isSubmitting}
        className={`w-full py-2.5 rounded font-semibold text-sm transition-all ${
          isFormValid && !form.isSubmitting
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        {form.isSubmitting ? 'Submitting...' : 'Submit Override Request'}
      </button>
    </form>
  );
};