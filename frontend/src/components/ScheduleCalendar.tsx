import React from 'react';
import { MOCK_SECTIONS } from '../types/schedule';
import { DAYS, getConflictingSectionIds, calculateBlockStyle } from '../utils/scheduleUtils';

export const ScheduleCalendar: React.FC = () => {
  const conflictingIds = getConflictingSectionIds(MOCK_SECTIONS);
  const hours = Array.from({ length: 11 }, (_, i) => i + 8);

  return (
    <div className="w-full max-w-5xl border rounded-lg overflow-hidden bg-white shadow-sm p-4">
      <h2 className="text-xl font-semibold mb-4">Course Schedule Display</h2>
      
      <div className="grid grid-cols-6 border-t border-l text-sm">
        <div className="p-2 border-r border-b font-medium text-gray-500 bg-gray-50">Time</div>
        {DAYS.map((day) => (
          <div key={day} className="p-2 border-r border-b font-semibold text-center bg-gray-50">
            {day}
          </div>
        ))}

        <div className="col-span-1 border-r bg-gray-50 text-xs text-gray-500">
          {hours.map((hour) => (
            <div key={hour} className="h-12 border-b p-1">
              {hour}:00
            </div>
          ))}
        </div>

        {DAYS.map((day) => (
          <div key={day} className="relative col-span-1 border-r h-[528px]">
            {hours.map((hour) => (
              <div key={hour} className="h-12 border-b border-gray-100" />
            ))}

            {MOCK_SECTIONS.flatMap((sec) =>
              sec.meetings
                .filter((m) => m.day === day)
                .map((m, idx) => {
                  const isConflict = conflictingIds.has(sec.id);
                  const position = calculateBlockStyle(m.startTime, m.endTime);

                  return (
                    <div
                      key={`${sec.id}-${idx}`}
                      style={{ position: 'absolute', width: '92%', left: '4%', ...position }}
                      className={`p-2 rounded text-xs border font-medium flex flex-col justify-between transition-all ${
                        isConflict
                          ? 'bg-red-50 border-red-500 text-red-900 z-10 shadow-md'
                          : 'bg-blue-50 border-blue-400 text-blue-900 z-0'
                      }`}
                    >
                      <div>
                        <div className="font-bold">{sec.courseCode}</div>
                        <div className="text-[10px] opacity-80">{sec.title}</div>
                      </div>
                      
                      {isConflict && (
                        <span className="inline-block px-1.5 py-0.5 mt-1 bg-red-600 text-white text-[9px] font-bold rounded">
                          ⚠️ Time Conflict
                        </span>
                      )}
                    </div>
                  );
                })
            )}
          </div>
        ))}
      </div>
    </div>
  );
};