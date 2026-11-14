
import { useState } from 'react';

type CompletedCourse = {
  code: string;
  title: string;
  grade: string;
  credits: number;
};

type Semester = {
  name: string;
  courses: CompletedCourse[];
};

const SAMPLE_HISTORY: Semester[] = [
  {
    name: 'Spring 2026',
    courses: [
      { code: 'COP 3530', title: 'Data Structures', grade: 'A', credits: 3 },
      { code: 'CDA 3203', title: 'Digital Systems', grade: 'B+', credits: 3 },
      { code: 'COT 3100', title: 'Discrete Structures', grade: 'A-', credits: 3 },
    ],
  },
  {
    name: 'Fall 2025',
    courses: [
      { code: 'COP 3014', title: 'Foundations of Computer Science', grade: 'A', credits: 3 },
      { code: 'MAC 2312', title: 'Calculus II', grade: 'B', credits: 4 },
      { code: 'PHY 2048', title: 'General Physics I', grade: 'B+', credits: 3 },
    ],
  },
];

export default function SemesterHistory() {
  const [semester, setSemester] = useState(SAMPLE_HISTORY[0].name);

  const selectedSemester = SAMPLE_HISTORY.find(
    (item) => item.name === semester
  )!;

  const totalCredits = selectedSemester.courses.reduce(
    (sum, course) => sum + course.credits,
    0
  );

  return (
    <section className="semester-history">
      <header className="semester-history-header">
        <h2>Semester History</h2>
        <p>Completed Coursework</p>
        <small>Sample academic records for prototype demonstration</small>
      </header>

      <div className="semester-history-toolbar">
        <label htmlFor="history-semester">Select Semester</label>
        <select
          id="history-semester"
          value={semester}
          onChange={(event) => setSemester(event.target.value)}
        >
          {SAMPLE_HISTORY.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </div>

      <div className="semester-history-summary">
        <div>
          <span>Completed Courses</span>
          <strong>{selectedSemester.courses.length}</strong>
        </div>
        <div>
          <span>Completed Credits</span>
          <strong>{totalCredits}</strong>
        </div>
        <div>
          <span>Semester</span>
          <strong>{selectedSemester.name}</strong>
        </div>
      </div>

      <div className="semester-history-table-wrap">
        <table className="semester-history-table">
          <thead>
            <tr>
              <th>Course</th>
              <th>Course Title</th>
              <th>Credits</th>
              <th>Grade</th>
            </tr>
          </thead>
          <tbody>
            {selectedSemester.courses.map((course) => (
              <tr key={course.code}>
                <td><strong>{course.code}</strong></td>
                <td>{course.title}</td>
                <td>{course.credits}</td>
                <td>
                  <span className="semester-grade">{course.grade}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="semester-history-note">
        These are fictional sample records, not verified FAU transcripts.
      </p>
    </section>
  );
}
