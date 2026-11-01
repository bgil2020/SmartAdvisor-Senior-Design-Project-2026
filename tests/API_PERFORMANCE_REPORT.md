# SmartAdvisor API Regression and Performance Report

## Test Environment

- Project: SmartAdvisor Prototype V2
- Testing method: FastAPI TestClient and Pytest
- Python: 3.13.14
- Performance runs: 5 requests per endpoint
- Environment: Local development computer

## Automated Regression Results

- Full test suite: 215 passed, 3 warnings
- Full suite duration: 17.51 seconds
- API regression and performance tests: 11 passed
- Previous CRN validation failures: Resolved

## API Performance Measurements

| Endpoint | Average (ms) | Maximum (ms) | HTTP Status |
|---|---:|---:|---|
| GET / | 6.92 | 11.66 | 200 |
| GET /courses | 210.91 | 251.72 | 200 |
| GET /sections | 193.40 | 216.72 | 200 |
| GET /alternatives?crn=99999999 | 6.84 | 9.81 | 404 (expected) |
| POST /compatibility | 167.56 | 194.32 | 200 |
| POST /conversation | 158.20 | 176.87 | 200 |

## Issues Identified and Resolved

Two regression tests initially failed because invalid
and empty CRN values returned HTTP 404 instead of 422.

Added numeric CRN validation to the /alternatives
endpoint. Both tests passed after the correction.

An initial full-suite run also failed because the
google-genai package was not installed locally.
Installing the project requirements resolved those failures.

## Performance Findings

GET /courses had the highest average response time
at 210.91 ms, followed by GET /sections at 193.40 ms.

No HTTP 500 responses occurred during the measured tests.

## Limitations

These results were measured using a local FastAPI
TestClient, not a deployed production environment.
They do not represent concurrent-user load testing.

The alternatives endpoint measurement covers an
expected 404 response, not a successful alternatives search.

## Conclusion

The SmartAdvisor Prototype V2 automated tests passed
after resolving the identified dependency and CRN
validation issues.

The measured endpoints showed no server errors during
the performance sanity checks. Further load testing
may be useful before production deployment.
