
# SmartAdvisor Backend Logging Guide

## Purpose

Backend logging helps the SmartAdvisor development team monitor API requests, identify errors, and troubleshoot problems during testing and demonstrations.

The logging system records request information in structured JSON format without including student information or API credentials.

## Logging Implementation

The logging system uses two files:

- `backend/logging_config.py` configures the JSON logger.
- `backend/api.py` contains the FastAPI middleware that records requests and errors.

Each log includes:

- Timestamp
- Logging level
- Event type
- HTTP method
- API endpoint
- HTTP status code
- Error category

## Starting the Backend

Open a terminal in the main SmartAdvisor project directory.

Run:

python -m uvicorn backend.api:app --reload --no-access-log

The `--no-access-log` option disables Uvicorn's default access logging, which could otherwise include query parameters.

## Example Successful Request

Request:

GET /courses

Example JSON log:

{"level":"INFO","event":"api_request","method":"GET","endpoint":"/courses","status_code":200,"error_category":null}

HTTP 200 indicates that the request succeeded.

## Example Validation Error

Request:

GET /alternatives

The request is missing the required CRN parameter.

Example JSON log:

{"level":"INFO","event":"api_request","method":"GET","endpoint":"/alternatives","status_code":422,"error_category":"CLIENT_ERROR"}

HTTP 422 indicates that the request failed input validation.

## Troubleshooting

1. Start the FastAPI backend and confirm that application startup completes.
2. Make a request to the endpoint being tested.
3. Check the terminal for a JSON log entry.
4. Identify the endpoint and HTTP status code.
5. Use the error category to determine the type of problem.
6. Inspect the corresponding backend function and run relevant automated tests.
7. Verify that the issue is resolved by repeating the request.

Common status codes:

- 200: Request succeeded.
- 400: Invalid request or unsupported input.
- 404: Resource not found.
- 422: Request validation failed.
- 500: Internal server error.

## Privacy and Security

The custom JSON logger does not record request bodies, query parameters, student names, passwords, or API keys.

Unknown URL paths are recorded as `unmatched_route` rather than storing their raw values.

Uvicorn should be started with `--no-access-log` to prevent its default access logs from recording full request URLs.

Developers should avoid manually logging sensitive information.

## Automated Testing

Run the dedicated logging tests:

python -m pytest tests/test_logging.py -v

Run the complete test suite:

python -m pytest -q

During local testing, all three logging tests passed. The existing 89 tests also passed before the dedicated logging tests were added.

## Current Limitations

The logging system currently runs in the local development copy of SmartAdvisor.

Deployment to the shared backend requires team review and updating the hosted server's startup configuration.

The logger records general error categories rather than detailed exception information to reduce the risk of exposing sensitive information.
