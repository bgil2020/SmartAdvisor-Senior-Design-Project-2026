
import type { RawSectionRecord } from '../services/api';

interface StudentDashboardProps {
  selectedSections: RawSectionRecord[];
  conflictCount: number;
  onRemoveCourse: (crn: string) => void;
}

export default function StudentDashboard({
  selectedSections,
  conflictCount,
  onRemoveCourse,
}: StudentDashboardProps) {
  const courses = Array.from(
    new Map(
      selectedSections.map((section) => [
        String(section.CRN),
        section,
      ])
    ).values()
  );

  return (
    <section className="student-dashboard">
      <div className="dashboard-heading">
        <h2>Student Dashboard</h2>
        <p>My Course Plan — SmartAdvisor</p>
      </div>

      <div className="dashboard-stats">
        <div className="dashboard-stat">
          <span>Planned Sections</span>
          <strong>{courses.length}</strong>
        </div>

        <div className="dashboard-stat">
          <span>Schedule Conflicts</span>
          <strong>{conflictCount}</strong>
        </div>

        <div className="dashboard-stat">
          <span>Course Plan Status</span>
          <strong>
            {courses.length === 0
              ? 'Not Started'
              : conflictCount > 0
                ? 'Needs Review'
                : 'Ready for Review'}
          </strong>
        </div>
      </div>

      <div className="dashboard-course-plan">
        <h3>My Selected Courses</h3>

        {courses.length === 0 ? (
          <p>
            No courses selected yet. Use the course catalog
            below to start building your schedule.
          </p>
        ) : (
          <div className="dashboard-course-list">
            {courses.map((course) => (
              <article
                className="dashboard-course-card"
                key={String(course.CRN)}
              >
                <div>
                  <h4>{course.COURSE}</h4>
                  <p>{course.TITLE}</p>
                  <small>
                    CRN: {course.CRN} | Section: {course.SECT}
                  </small>
                  <p>
                    {course.DAYS || 'Days TBA'} |{' '}
                    {course['BEG TIME'] || 'Time TBA'} –{' '}
                    {course['END TIME'] || 'Time TBA'}
                  </p>
                  <small>
                    {course.METHOD || 'Method TBA'}
                  </small>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    onRemoveCourse(String(course.CRN))
                  }
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        )}
      </div>

      <p className="dashboard-disclaimer">
        Preliminary course planning only. This dashboard does
        not register students for FAU classes.
      </p>
    </section>
  );
}

