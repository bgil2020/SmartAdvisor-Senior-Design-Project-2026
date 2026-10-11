# SmartAdvisor Backend

This folder contains the backend modules for SmartAdvisor, an academic course-planning application designed to help students identify scheduling conflicts and find alternative course sections.

## Project Structure

```text
SmartAdvisor_Backend/
├── backend/
│   ├── __init__.py
│   ├── api.py
│   ├── section_retriever.py
│   ├── meeting_time_normalizer.py
│   ├── overlap_detector.py
│   ├── alternative_section_search.py
│   └── result_formatter.py
├── data/
│   └── FAU_Courses.xlsx
├── tests/
│   ├── test_api.py
│   ├── test_meeting_time_normalizer.py
│   ├── test_overlap_detector.py
│   └── test_alternative_section_search.py
├── .env.example
├── smartadvisor.py
├── requirements.txt
└── README.md
```

## Setup in VS Code

1. Open the SmartAdvisor_Backend folder in VS Code.
2. Open Terminal → New Terminal.
3. Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Start the FastAPI server:

```bash
python -m uvicorn backend.api:app --reload
```

5. Open the API documentation in your browser:

http://127.0.0.1:8000/docs

## Health Check

The backend provides a health endpoint to verify that the API is running.

Open:

http://127.0.0.1:8000/health

Expected response:

```json
{
  "status": "healthy",
  "application": "SmartAdvisor",
  "message": "Backend API is running successfully."
}
```

## API Features

The SmartAdvisor backend provides the following functionality:

- Course and section retrieval
- Filtering courses by CRN, department, term, and modality
- Meeting-time normalization
- Scheduling conflict detection
- Alternative section search
- Health-check endpoint

The FastAPI application includes Swagger/OpenAPI documentation for testing available endpoints.

## Alternative Section Search

When a selected class needs a replacement, the backend:

1. Retrieves the original section by CRN.
2. Searches the FAU dataset for sections of the same course.
3. Keeps sections within the same term.
4. Excludes the original CRN.
5. Removes sections without available seats.
6. Checks candidate sections against other selected classes.
7. Excludes sections with scheduling conflicts.
8. Returns up to three available alternatives.

## Automated Testing

The project uses pytest to verify backend functionality.

To run all tests:

```bash
python -m pytest -v
```

The tests cover course retrieval, meeting-time normalization, scheduling conflicts, and alternative section search.

## Environment Configuration

The `.env.example` file provides a template for application configuration.

It includes:

- Application name
- Development environment
- API host and port
- Supabase URL placeholder
- Supabase key placeholder

Actual database credentials should not be committed to GitHub.

## Spreadsheet Fields Used

- CRN
- COURSE
- SECT
- TERM
- TITLE
- DAYS
- BEG TIME
- END TIME
- ENRL REMN
- CAMPUS
- INSTRUCTOR
- METHOD

The included workbook is the FAU course-section dataset supplied for the project.