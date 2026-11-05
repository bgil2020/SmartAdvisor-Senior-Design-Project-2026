# SmartAdvisor Demo Reliability Report

## Purpose
This report documents local database reliability testing, backup and recovery verification, and backend API availability testing for the SmartAdvisor prototype demonstration.

## Test Environment
- Working branch: `jeffrey-demo-reliability` (created from the team's `main` branch)
- Operating system: Windows
- Database: Local PostgreSQL 17, `smartadvisor_demo`
- Recovery-test database: `smartadvisor_restore_test`
- Backend: Python FastAPI
- Course API data source: `data/FAU_Courses.xlsx`
- Testing dates: November 4–5, 2026

The PostgreSQL demo database is separate from the Excel-backed FastAPI course API. No shared Supabase database was modified in these tests.

## Three Demo Database Cycles

| Check | Cycle 1 | Cycle 2 | Cycle 3 |
|---|---|---|---|
| Seed script completed | Passed | Passed | Passed |
| Demo courses inserted | 3 | 3 | 3 |
| Demo sections inserted | 3 | 3 | 3 |
| Total courses after seed | 4 | 4 | 4 |
| Total sections after seed | 3 | 3 | 3 |
| `TEST_SAFE101` preserved after seed | Yes | Yes | Yes |
| Reset script completed | Passed | Passed | Passed |
| Total courses after reset | 1 | 1 | 1 |
| Total sections after reset | 0 | 0 | 0 |
| `TEST_SAFE101` preserved after reset | Yes | Yes | Yes |

All three consecutive local PostgreSQL seed/reset cycles completed successfully. These were database demonstration cycles, not three independently verified full frontend-to-backend demonstration runs.

## Backup and Recovery Test

A PostgreSQL custom-format backup was created before testing using `pg_dump`.

- Backup filename: `smartadvisor_demo_before_tests.backup`
- Backup location: `Documents/SmartAdvisor-Demo-Backups/` (outside the Git repository)
- File size: 8,796 bytes
- Backup archive contents inspected using `pg_restore --list`
- Backup restored successfully into the separate `smartadvisor_restore_test` database

### Restored Record Counts

| Table | Original | Restored |
|---|---:|---:|
| courses | 1 | 1 |
| sections | 0 | 0 |
| risk_rules | 0 | 0 |
| student_profiles | 0 | 0 |

The restore test verified that the backup could be restored into a separate local database and that the restored table counts matched the original database. The original database was not overwritten.

## Backend API and Port-Conflict Recovery

- Initial attempt to start FastAPI on port 8001 encountered Windows error 10048 because the port was already in use.
- Started the backend using port 8002 instead.
- Swagger documentation opened successfully at `http://127.0.0.1:8002/docs`.
- `GET /courses` returned HTTP 200 and 913 FAU course-section records.
- Backend API automated check: `tests/test_api.py` completed with 5 passed, 1 warning.

This verifies local backend startup and a working fallback port. A full frontend demonstration and an offline operation test remain pending.

## Current Reliability Results

| Requirement | Status |
|---|---|
| Three local database seed/reset cycles | Passed |
| Preserve unrelated test record | Passed |
| Create local database backup | Passed |
| Restore backup into a separate database | Passed |
| Run backend API tests | Passed (5 tests) |
| Recover from occupied port by switching ports | Passed |
| Full frontend-to-backend demo repeated three times | Not yet verified |
| Offline frontend fallback | Not yet verified |

## Safety and Limitations

- All database modifications were limited to local `smartadvisor_demo`.
- The team's shared Supabase database was not modified.
- The FastAPI course endpoints use an Excel dataset, not the local PostgreSQL demo database.
- Backup files and database passwords must not be committed to GitHub.
- The backup restoration was tested locally; this does not establish cloud production disaster recovery.

## Remaining Work

1. Document API restart and fallback instructions in the demo runbook.
2. Verify the frontend connects to the backend using the chosen fallback port.
3. If required for the demonstration, complete and document three full frontend-to-backend demo runs.
4. Test the intended offline fallback procedure.
5. Submit the reliability report with screenshots of the seed/reset runs, restored record counts, and HTTP 200 response.