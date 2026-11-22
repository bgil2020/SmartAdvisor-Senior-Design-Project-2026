# SmartAdvisor — Backend Presentation Speaker Notes

## Slide 1 — Backend Architecture

Hello everyone. Today, I will explain the backend architecture of our SmartAdvisor project and the testing we completed.

Our SmartAdvisor application uses React and TypeScript for the frontend and Python with FastAPI for the backend.

The backend handles course retrieval, schedule conflict detection, alternative section searches, course compatibility evaluation, and conversational request processing.

Our current course information comes from Excel datasets, while Supabase integration is prepared but not active in the normal application runtime.

## Slide 2 — API and Data Flow

When a student searches for a course, the React frontend sends an HTTP request to our FastAPI backend.

The backend uses the Section Retriever to search the FAU course dataset and returns matching course information as a JSON response.

For scheduling conflicts, the Overlap Detector compares meeting days and times. The Alternative Section Search can then identify replacement sections that do not conflict with the student's existing schedule.

This allows students to search for available sections and review scheduling alternatives.

## Slide 3 — Automated Testing

To verify the system, I ran our automated backend and frontend tests.

The backend completed **253 tests successfully**, with zero failures and three warnings.

The frontend completed **32 tests successfully**, also with zero failures.

Together, our project passed **285 automated tests**, with no test failures.

I also verified that the frontend successfully completed its TypeScript compilation and production build.

## Slide 4 — Demo Reliability and Recovery

I performed additional reliability checks to help prepare SmartAdvisor for our demonstration.

I completed three consecutive database seed-and-reset cycles and verified that existing unrelated test data was preserved.

I also created a PostgreSQL database backup and successfully restored it into a separate test database.

During testing, I encountered a backend port conflict. I resolved it by starting FastAPI on port 8002 and configuring the React frontend to communicate with that port.

I also tested local course searching with Wi-Fi disabled, and the frontend was still able to retrieve course information from the local backend.

These checks give us documented recovery options if we encounter local setup problems during the demonstration.

## Slide 5 — Summary

In summary, SmartAdvisor has a working FastAPI backend connected to our React frontend.

Our verified local testing results include 285 passing automated tests, a successful frontend build, and database backup and recovery checks.

We have also documented the system architecture, API data flow, and fallback instructions to support our upcoming demonstration.

Thank you.