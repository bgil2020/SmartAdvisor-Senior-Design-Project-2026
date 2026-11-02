
# SmartAdvisor API Regression and Performance Report

## Test Environment

- Project: SmartAdvisor Group 17
- Branch: jeffrey-api-regression
- Framework: FastAPI TestClient and pytest
- Testing method: Local automated API requests
- Performance samples: 5 requests per endpoint

## Regression Test Results

Existing automated test suite:
- 138 passed
- 0 failed
- 3 warnings

Additional API regression tests:
- 8 passed
- 0 failed
- 1 warning

## Performance Results

| Endpoint | Average (ms) | Maximum (ms) | Status |
|---|---:|---:|---|
| GET / | 23.62 | 68.22 | 200 |
| GET /courses | 359.64 | 406.64 | 200 |
| GET /sections | 466.26 | 615.41 | 200 |
| GET /alternatives?crn=99999999 | 43.92 | 66.58 | 404 (expected) |
| POST /compatibility | 295.03 | 353.37 | 200 |
| POST /conversation | 319.80 | 352.99 | 200 |
- POST /compatibility returned HTTP 200 in all 5 requests.
- POST /conversation returned HTTP 200 in all 5 requests and successfully executed the compatibility engine.
- No HTTP 500 errors were observed across the six tested request paths.
## Findings

- No server errors were observed during the performance checks.
- GET /sections had the highest average response time.
- GET /courses had the second-highest average response time.
- The nonexistent CRN scenario correctly returned HTTP 404.

## Issues to Monitor

1. GET /sections: highest measured average latency (466.26 ms).
2. GET /courses: second-highest measured average latency (359.64 ms).
3. Testing-library deprecation warnings should be reviewed separately.

These measurements do not establish that an endpoint violates a performance requirement. They identify candidates for further investigation.

## Limitations

- Measurements were collected using the local FastAPI TestClient.
- Only five requests were collected per endpoint.
- Concurrent-user load testing was not performed.
- POST /compatibility and POST /conversation performance checks are pending.
- The current course endpoints use the FAU Excel dataset rather than the local PostgreSQL demo records.

## Current Status

Initial API regression and performance sanity checks passed.

Further POST endpoint coverage and issue triage are pending.
