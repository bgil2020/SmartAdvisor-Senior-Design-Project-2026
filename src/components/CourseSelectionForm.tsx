import React, { useState } from 'react';

export const CourseSelectionForm: React.FC = () => {
  const [major, setMajor] = useState('');
  const [modality, setModality] = useState('HYBRID');

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm max-w-xl mb-6">
      <h3 className="font-bold text-lg mb-3">Student Course Selection & Preferences</h3>
      <div className="space-y-3 text-sm">
        <div>
          <label className="block font-medium mb-1">Major / Program</label>
          <input
            type="text"
            value={major}
            onChange={(e) => setMajor(e.target.value)}
            placeholder="e.g., Computer Science"
            className="w-full p-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block font-medium mb-1">Modality Preference</label>
          <select 
            value={modality} 
            onChange={(e) => setModality(e.target.value)} 
            className="w-full p-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="IN_PERSON">In Person</option>
            <option value="ONLINE">Online</option>
            <option value="HYBRID">Hybrid</option>
          </select>
        </div>
      </div>
    </div>
  );
};