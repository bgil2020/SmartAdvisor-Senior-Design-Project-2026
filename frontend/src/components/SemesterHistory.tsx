
import { useState, useEffect, type ChangeEvent } from 'react';
import { supabase } from '../lib/supabase';
import '../App.css';

type Course = {
  code: string;
  title: string;
  grade: string;
  credits: number;
  status: string;
};

type Semester = {
  name: string;
  courses: Course[];
};


type DarsResponse = {
  account_id: string;
  degree: string | null;
  semesters: Record<string, {
    course: string;
    title: string;
    grade: string;
    credits: number;
    status: string;
  }[]>;
};


const SAMPLE_HISTORY: Semester[] = [
  {
    name: 'Spring 2026',
    courses: [
      {
        code: 'COP 3530',
        title: 'Data Structures',
        grade: 'A',
        credits: 3,
        status: 'Completed'
      },
      {
        code: 'CDA 3203',
        title: 'Digital Systems',
        grade: 'B+',
        credits: 3,
        status: 'Completed'
      },
      {
        code: 'COT 3100',
        title: 'Discrete Structures',
        grade: 'A-',
        credits: 3,
        status: 'Completed'
      }
    ]
  },
  {
    name: 'Fall 2025',
    courses: [
      {
        code: 'COP 3014',
        title: 'Foundations of Computer Science',
        grade: 'A',
        credits: 3,
        status: 'Completed'
      },
      {
        code: 'MAC 2312',
        title: 'Calculus II',
        grade: 'B',
        credits: 4,
        status: 'Completed'
      },
      {
        code: 'PHY 2048',
        title: 'General Physics I',
        grade: 'B+',
        credits: 3,
        status: 'Completed'
      }
    ]
  }
];

const API_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'
).replace(/\/$/, '');


type SemesterHistoryProps = {
  onHistorySaved?: () => void;
};

export default function SemesterHistory({
  onHistorySaved
}: SemesterHistoryProps) {
  const [history, setHistory] = useState<Semester[]>(SAMPLE_HISTORY);
  const [semester, setSemester] = useState('Spring 2026');
  const [student, setStudent] = useState<DarsResponse | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [visibleGrades, setVisibleGrades] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const selectedSemester = history.find(
    item => item.name === semester
  );

  const courses = selectedSemester?.courses || [];

  const completedCourses = courses.filter(
    course => course.status === 'Completed'
  );

  const totalCredits = completedCourses.reduce(
    (sum, course) => sum + course.credits,
    0
  );

  const displayedCourses = expanded
    ? courses
    : courses.slice(0, 3);
  
  useEffect(() => {
    let active = true;

    const loadSavedHistory = async () => {
      try {
        const { data: authData, error: authError } =
          await supabase.auth.getUser();

        if (authError || !authData.user) return;

        const userId = authData.user.id;

        const { data: profile, error: profileError } =
          await supabase
            .from('student_dars_profiles')
            .select('degree')
            .eq('user_id', userId)
            .maybeSingle();

        if (profileError) throw profileError;
        if (!profile || !active) return;

        const { data: records, error: recordsError } =
          await supabase
            .from('student_course_history')
            .select('*')
            .eq('user_id', userId)
            .order('id', { ascending: true });

        if (recordsError) throw recordsError;

        if (!records || records.length === 0 || !active) {
          return;
        }

        const grouped: DarsResponse['semesters'] = {};

        records.forEach(record => {
          if (!grouped[record.semester]) {
            grouped[record.semester] = [];
          }

          grouped[record.semester].push({
            course: record.course_code,
            title: record.course_title,
            credits: Number(record.credits),
            grade: record.grade,
            status: record.status
          });
        });

        const importedHistory: Semester[] =
          Object.entries(grouped).map(([name, courses]) => ({
            name,
            courses: courses.map(course => ({
              code: course.course,
              title: course.title,
              credits: course.credits,
              grade: course.grade,
              status: course.status
            }))
          }));

        const semesterOrder: Record<string, number> = {
          Spring: 1,
          Summer: 2,
          Fall: 3
        };

        importedHistory.sort((a, b) => {
          const [seasonA, yearA] = a.name.split(' ');
          const [seasonB, yearB] = b.name.split(' ');

          return (
            Number(yearB) - Number(yearA) ||
            (semesterOrder[seasonB] || 0) -
            (semesterOrder[seasonA] || 0)
          );
        });

        if (!active) return;

        
setStudent({
  account_id: userId,
  degree: profile.degree,
  semesters: grouped
});


        setHistory(importedHistory);
        setSemester(importedHistory[0].name);
        setExpanded(false);
        setVisibleGrades([]);
        setSaved(true);
        setMessage('Saved DARS history loaded successfully.');

      } catch (err) {
        if (active) {
          setError('Unable to load saved DARS history.');
        }
      }
    };

    loadSavedHistory();

    return () => {
      active = false;
    };
  }, []);

  const toggleGrade = (key: string) => {
    setVisibleGrades(previous =>
      previous.includes(key)
        ? previous.filter(item => item !== key)
        : [...previous, key]
    );
  };
  
  const handleSaveHistory = async () => {
    if (!student || saving) return;

    const confirmed = window.confirm(
      'Save this DARS history? This will replace your previously saved academic history.'
    );

    if (!confirmed) return;

    setSaving(true);
    setError('');
    setMessage('');

    try {
      const { data: authData, error: authError } =
        await supabase.auth.getUser();

      if (authError || !authData.user) {
        throw new Error('Please log in again.');
      }

      if (authData.user.id !== student.account_id) {
        throw new Error('Student account mismatch.');
      }

      const records = history.flatMap(item =>
        item.courses.map(course => ({
          semester: item.name,
          course_code: course.code,
          course_title: course.title,
          credits: course.credits,
          grade: course.grade,
          status: course.status
        }))
      );

      
const { error: saveError } = await supabase.rpc(
  'save_dars_history',
  {
    p_degree: student.degree,
    p_courses: records
  }
);


      if (saveError) throw saveError;

      setSaved(true);
      setMessage('DARS history saved successfully!');
      onHistorySaved?.();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (err as { message?: string })?.message
            || 'Unable to save DARS history.'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (
    event: ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setError('');
    setMessage('');

    if (
      file.type !== 'application/pdf' ||
      !file.name.toLowerCase().endsWith('.pdf')
    ) {
      setError('Please select a PDF file.');
      event.target.value = '';
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError('PDF must be smaller than 5 MB.');
      event.target.value = '';
      return;
    }

    setLoading(true);

    try {
      const { data: sessionData, error: sessionError } =
        await supabase.auth.getSession();

      if (sessionError) throw sessionError;

      const token = sessionData.session?.access_token;

      if (!token) {
        throw new Error('Please log in before uploading your DARS.');
      }

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(
        `${API_URL}/dars/upload-preview`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`
          },
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error(
          response.status === 401 || response.status === 403
            ? 'Your login session could not be verified.'
            : `DARS upload failed (${response.status}).`
        );
      }

      const data: DarsResponse = await response.json();

      const importedHistory: Semester[] = Object.entries(
        data.semesters
      ).map(([name, records]) => ({
        name,
        courses: records.map(record => ({
          code: record.course,
          title: record.title,
          grade: record.grade,
          credits: record.credits,
          status: record.status
        }))
      }));

      if (importedHistory.length === 0) {
        throw new Error('No semester records were found in the PDF.');
      }

      const semesterOrder: Record<string, number> = {
        Spring: 1,
        Summer: 2,
        Fall: 3
      };

      importedHistory.sort((a, b) => {
        const [seasonA, yearA] = a.name.split(' ');
        const [seasonB, yearB] = b.name.split(' ');

        return (
          Number(yearB) - Number(yearA) ||
          (semesterOrder[seasonB] || 0) -
          (semesterOrder[seasonA] || 0)
        );
      });

      setHistory(importedHistory);
      setSaved(false);
      setStudent(data);
      setSemester(importedHistory[0].name);
      setExpanded(false);
      setVisibleGrades([]);
      setMessage('DARS imported successfully for preview.');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to upload DARS.'
      );
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  return (
    <section className="semester-history">
      <header className="semester-history-header">
        <h2>Semester History</h2>
        <p>Completed Coursework</p>
        <small>
          {student
            ? 'Imported academic records from DARS'
            : 'Sample academic records for prototype demonstration'}
        </small>
      </header>

      <div className="semester-history-toolbar">
        <label
          htmlFor="dars-file"
          style={{ cursor: 'pointer' }}
        >
          Upload DARS PDF
        </label>

        <input
          id="dars-file"
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleUpload}
          disabled={loading}
        />

        {loading && <p role="status">Reading DARS PDF...</p>}

        {student && (
          <button
            type="button"
            onClick={handleSaveHistory}
            disabled={saving || loading || saved}
            style={{
              padding: '12px 20px',
              marginTop: '12px',
              backgroundColor: saved ? '#166534' : '#17365d',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              cursor: saving || loading || saved
                ? 'default'
                : 'pointer'
            }}
          >
            {saving
              ? 'Saving History...'
              : saved
                ? '✓ History Saved'
                : 'Save DARS History'}
          </button>
        )}


        {error && (
          <p role="alert" style={{ color: '#dc2626' }}>
            {error}
          </p>
        )}

        {message && (
          <p role="status" style={{ color: '#166534' }}>
            {message}
          </p>
        )}
      </div>

      
      {student && (
        <div className="semester-history-summary">
          <div>
            <span>Degree</span>
            <strong>{student.degree || 'Not found'}</strong>
          </div>
        </div>
      )}


      <div className="semester-history-toolbar">
        <label htmlFor="history-semester">
          Select Semester
        </label>

        <select
          id="history-semester"
          value={semester}
          onChange={event => {
            setSemester(event.target.value);
            setExpanded(false);
            setVisibleGrades([]);
          }}
        >
          {history.map(item => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </div>

          
<div className="semester-history-summary">
  <div>
    <span>Total Courses</span>
    <strong>{courses.length}</strong>
  </div>

  <div>
    <span>Completed Courses</span>
    <strong style={{ color: '#166534' }}>
      {completedCourses.length}
    </strong>
  </div>

  <div>
    <span>Earned Credits</span>
    <strong>{totalCredits}</strong>
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
            {displayedCourses.map((course, index) => {
              const key = `${semester}-${index}`;

              const isVisible = visibleGrades.includes(key);

              return (
                <tr key={key}>
                  <td>
                    <strong>{course.code}</strong>
                  </td>

                  <td>
                    {course.title}
                    
<small
  style={{
    display: 'table',
    marginTop: '6px',
    padding: '4px 10px',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 600,
    backgroundColor:
      course.status === 'Completed'
        ? '#dcfce7'
        : course.status === 'In Progress'
        ? '#dbeafe'
        : '#fee2e2',
    color:
      course.status === 'Completed'
        ? '#166534'
        : course.status === 'In Progress'
        ? '#1d4ed8'
        : '#991b1b'
  }}
>
  {course.status === 'Completed'
    ? '✓ Completed'
    : course.status}
</small>

                  </td>

                  <td>{course.credits}</td>

                  <td>
                    <span className="semester-grade">
                      {isVisible ? course.grade : '•••'}
                    </span>

                    <button
                      type="button"
                      onClick={() => toggleGrade(key)}
                      aria-label={
                        isVisible ? 'Hide grade' : 'Show grade'
                      }
                      title={
                        isVisible ? 'Hide grade' : 'Show grade'
                      }
                      style={{
                        marginLeft: '10px',
                        border: 'none',
                        background: 'transparent',
                        cursor: 'pointer',
                        fontSize: '18px'
                      }}
                    >
                      
<svg
  width="20"
  height="20"
  viewBox="0 0 24 24"
  fill="none"
  stroke="#64748b"
  strokeWidth="1.8"
  strokeLinecap="round"
  strokeLinejoin="round"
>
  <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
  <circle cx="12" cy="12" r="3" />
  {isVisible && <path d="M3 3l18 18" />}
</svg>

                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {courses.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: '16px',
            padding: '10px 18px',
            background: '#17365d',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer'
          }}
        >
          {expanded ? '▲ Show Less' : '▼ Show All Courses'}
        </button>
      )}

      
<p className="semester-history-note">
  {student
    ? saved
      ? 'DARS history saved. Verify records before academic planning.'
      : 'Imported DARS records are a preview and have not been saved.'
    : 'These are fictional sample records, not verified FAU transcripts.'}
</p>

    </section>
  );
}
