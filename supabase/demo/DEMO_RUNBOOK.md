
# SmartAdvisor Demo Setup Runbook

## Purpose

This guide explains how to prepare, seed, test, and reset the SmartAdvisor demonstration database.

The procedure uses a local PostgreSQL database named `smartadvisor_demo` to protect the team's shared Supabase environment.

## Requirements

- Windows with PowerShell
- PostgreSQL 17
- SmartAdvisor GitHub repository
- Access to the local PostgreSQL server
- PostgreSQL database credentials

## 1. Prepare PostgreSQL

Install PostgreSQL 17 and ensure the database server is running.

Open PowerShell in the SmartAdvisor project folder.

Connect to PostgreSQL:

    & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h 127.0.0.1 -p 5432 -d postgres

Create the demo database if it does not already exist:

    CREATE DATABASE smartadvisor_demo;

Connect to the demo database:

    \c smartadvisor_demo

Create the four SmartAdvisor database tables:

    \i 'supabase/migrations/20261009_initial_schema.sql'

The migration creates:

- courses
- sections
- risk_rules
- student_profiles

Exit PostgreSQL:

    \q

## 2. Seed Demo Data

From PowerShell in the project root, run:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\supabase\demo\seed.ps1"

Enter the local PostgreSQL password when prompted.

Expected results:

- Three demo courses inserted
- Three demo sections inserted
- Transaction committed successfully

Running the seed again should not create duplicates.

## 3. Reset Demo Data

Run:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\supabase\demo\reset.ps1"

Enter the PostgreSQL password when prompted.

Expected results:

- Three demo sections removed
- Three demo courses removed
- No unrelated data modified

## 4. Verify Database Records

Connect to the local demo database:

    & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h 127.0.0.1 -p 5432 -d smartadvisor_demo

Run:

    SELECT COUNT(*) FROM public.courses;
    SELECT COUNT(*) FROM public.sections;
    SELECT COUNT(*) FROM public.risk_rules;
    SELECT COUNT(*) FROM public.student_profiles;

After seeding, the courses and sections counts should each be 3 in a new empty demo database.

After resetting, all four tables should contain 0 records in a new empty demo database.

## 5. Start SmartAdvisor Backend

Install Python dependencies:

    python -m pip install -r requirements.txt

Start the backend:

    python -m uvicorn backend.api:app --reload

Open:

    http://127.0.0.1:8000/docs

Test the available API endpoints.

Important: The existing FastAPI course endpoints currently use the FAU Excel dataset, not the local demo PostgreSQL database. Seeding the demo database does not automatically change the API responses.

## 6. Safety Rules

- Use only the local `smartadvisor_demo` database.
- Do not run seed or reset scripts against the team's production Supabase database.
- Do not commit database passwords or API keys.
- Do not disable Row Level Security in Supabase.
- Do not run the reset scripts against shared student data.

## 7. Troubleshooting

**Password authentication failed**

Verify the local PostgreSQL username and password.

**psql.exe not found**

Confirm PostgreSQL 17 is installed.

**Database does not exist**

Create `smartadvisor_demo` before running the scripts.

**SQL table does not exist**

Run the initial schema migration.

**PowerShell execution policy error**

Use the documented `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` command.

## 8. Teammate Verification

A teammate must independently follow this runbook and verify:

- Local database creation
- Schema migration
- Successful seed
- Correct demo record counts
- Successful reset
- Zero demo records after reset

Record the teammate's name, test date, screenshots, and any difficulties encountered.

## Current Verification Status
| Offline local course-search fallback | Passed — React frontend and FastAPI backend successfully retrieved course information with Wi-Fi disabled on November 5, 2026. |


## Current Verification Status

Local testing completed successfully.

### Tests Passed

- Created the local smartadvisor_demo database.
- Created all four SmartAdvisor database tables.
- Inserted 3 demo courses and 3 demo sections.
- Ran seed.sql twice without creating duplicates.
- Successfully executed automated seed.ps1.
- Successfully executed automated reset.ps1.
- Verified that all demo records were removed.
- Confirmed that unrelated course TEST_SAFE101 was preserved.
- Ran reset.ps1 twice without errors.
- Successfully launched FastAPI and opened Swagger UI.

- Verified the Render cloud backend deployment.
- Confirmed the cloud Swagger UI loads successfully.
- Executed GET /courses on Render.
- Received HTTP 200 (successful response).

### Cloud Deployment Verification

Backend URL:
https://smartadvisor-group17-demo.onrender.com

Swagger UI:
https://smartadvisor-group17-demo.onrender.com/docs

Tested endpoint: GET /courses
Result: HTTP 200
Status: Passed

Note: This verifies the deployed backend API.
The local PostgreSQL demo database is separate
from the Render deployment.


### Pending Verification

- Verify the deployed cloud application.
- Have a teammate independently follow this runbook.
- Record teammate test results and screenshots.
- Complete additional safeguards before considering the scripts suitable for a shared database.

### Database Safety

All database modification tests were performed on the local
PostgreSQL database named smartadvisor_demo.

The team's SmartAdvisor-Development Supabase database was not
modified during these tests.


## 9. Demo Recovery and Fallback Procedures

### Backend API Recovery

If the local FastAPI backend stops during the demonstration:

1. Open a PowerShell terminal in the SmartAdvisor repository root.
2. Restart the backend:

   ```powershell
   python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
   ```

3. Open `http://127.0.0.1:8000/docs` and test `GET /courses`.
4. If port 8000 is unavailable, use another free port, for example:

   ```powershell
   python -m uvicorn backend.api:app --host 127.0.0.1 --port 8002
   ```

5. Open `http://127.0.0.1:8002/docs` and verify that `GET /courses` returns HTTP 200.

The port 8002 fallback was tested successfully on November 5, 2026. `GET /courses` returned HTTP 200 and 913 FAU course-section records.

### Frontend Recovery

If the backend port changes, the frontend must use the same API address. For a local Vite frontend, set `VITE_API_URL=http://127.0.0.1:8002` in `frontend/.env.local`, then restart the frontend development server:

```powershell
cd frontend
npm.cmd run dev
```

Open the local Vite URL displayed in the terminal (typically `http://localhost:5173`) and test course search. This frontend fallback has not yet been verified during the current reliability testing.

### Local Database Backup Recovery

The PostgreSQL demo data is separate from the Excel-backed FastAPI course API.

A backup was created outside the Git repository at:

`Documents/SmartAdvisor-Demo-Backups/smartadvisor_demo_before_tests.backup`

To avoid overwriting the original demo database, restore into a new, empty local recovery database using PostgreSQL 17:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -h 127.0.0.1 -p 5432 smartadvisor_restore_test
```

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -U postgres -h 127.0.0.1 -p 5432 -d smartadvisor_restore_test --exit-on-error --no-owner --no-acl "$HOME\Documents\SmartAdvisor-Demo-Backups\smartadvisor_demo_before_tests.backup"
```

Create and restore into an empty database; if `smartadvisor_restore_test` already exists, use a different new name rather than overwriting it. Never run the restore on a shared database.

The recovery test succeeded on November 4, 2026. The restored database contained 1 course, 0 sections, 0 risk rules, and 0 student profiles, matching the original backup.

### Offline Demonstration Fallback

The SmartAdvisor course API uses the local `data/FAU_Courses.xlsx` dataset and does not require the shared Supabase database for course retrieval. The backend can therefore be started locally without relying on the cloud database, provided its dependencies and source files are available.

Before the demonstration, verify that the local frontend can connect to the local FastAPI backend and complete a representative course-search workflow without cloud services. Keep the approved demo source version and a prerecorded demonstration available as additional presentation fallbacks if the team prepares them.

Offline frontend operation has not yet been tested as part of this reliability task. Do not claim the offline fallback is fully verified until a complete local demonstration succeeds without internet connectivity.

### Reliability Evidence

See `docs/DEMO_RELIABILITY_REPORT.md` for the three completed PostgreSQL seed/reset cycles, database backup/restore verification, and backend API recovery results. All database modifications were performed on the local `smartadvisor_demo` database, not the team's shared Supabase database.