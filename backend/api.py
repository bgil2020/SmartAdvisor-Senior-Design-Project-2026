
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
import os
from pathlib import Path
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

from .alternative_section_search import find_alternative_sections
from .compatibility_router import router as compatibility_router
from .conversational_router import router as conversational_router
from .logging_config import get_api_logger

app = FastAPI(
    title="SmartAdvisor API",
    description="Backend API for retrieving FAU course and section data.",
    version="1.0.0",
)

api_logger = get_api_logger()


class ApiLoggingMiddleware:
    """Pure ASGI request logging without buffering response bodies."""

    def __init__(self, app, logger):
        self.app = app
        self.logger = logger

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        status_code = 500

        async def send_with_status(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception:
            self._write(scope, 500, "api_error", "UNHANDLED_EXCEPTION")
            raise
        else:
            category = "SERVER_ERROR" if status_code >= 500 else "CLIENT_ERROR" if status_code >= 400 else None
            self._write(scope, status_code, "api_request", category)

    def _write(self, scope, status_code, event, category):
        route = scope.get("route")
        self.logger.info(
            "API request completed",
            extra={
                "event": event,
                "method": scope.get("method"),
                "endpoint": getattr(route, "path", "unmatched_route"),
                "status_code": status_code,
                "error_category": category,
            },
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "SMARTADVISOR_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(ApiLoggingMiddleware, logger=api_logger)

app.include_router(compatibility_router)
app.include_router(conversational_router)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def find_dataset():
    if not DATA_DIR.exists():
        raise RuntimeError(
            f"Data folder was not found: {DATA_DIR}"
        )

    files = list(DATA_DIR.glob("*.xlsx"))
    files += list(DATA_DIR.glob("*.xls"))
    files += list(DATA_DIR.glob("*.csv"))

    if not files:
        raise RuntimeError(
            "No Excel or CSV course dataset was found inside the data folder."
        )

    return files[0]


def load_courses():
    file_path = find_dataset()

    if file_path.suffix.lower() == ".csv":
        dataframe = pd.read_csv(file_path)
    else:
        dataframe = pd.read_excel(file_path)

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    return dataframe


courses = load_courses()


def clean_value(value):
    if pd.isna(value):
        return None

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def dataframe_to_records(dataframe):
    records = []

    for _, row in dataframe.iterrows():
        record = {}

        for column in dataframe.columns:
            record[column] = clean_value(row[column])

        records.append(record)

    return records


def get_column(*possible_names):
    column_map = {
        str(column).strip().upper(): column
        for column in courses.columns
    }

    for name in possible_names:
        normalized_name = name.strip().upper()

        if normalized_name in column_map:
            return column_map[normalized_name]

    return None


def require_column(*possible_names):
    column = get_column(*possible_names)

    if column is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Required dataset column was not found. "
                f"Expected one of: {possible_names}"
            ),
        )

    return column


def text_filter(dataframe, column, value):
    return dataframe[
        dataframe[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        == value.strip().casefold()
    ]


@app.get("/")
def home():
    return {
        "application": "SmartAdvisor",
        "message": "SmartAdvisor API is running.",
        "records_loaded": len(courses),
    }


@app.get("/courses")
def get_courses(
    term: str | None = Query(default=None),
    department: str | None = Query(default=None),
    modality: str | None = Query(default=None),
):
    results = courses.copy()

    if term:
        term_column = require_column("TERM")

        results = text_filter(
            results,
            term_column,
            term,
        )

    if department:
        course_column = require_column(
            "COURSE",
            "COURSE ID",
        )

        department = department.strip().upper()

        results = results[
            results[course_column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .str.startswith(department)
        ]

    if modality:
        method_column = get_column(
            "METHOD",
            "INSTRUCTION METHOD",
            "INSTRUCTIONAL METHOD",
            "MODALITY",
        )

        campus_column = get_column("CAMPUS")

        if method_column is None and campus_column is None:
            raise HTTPException(
                status_code=500,
                detail="The dataset does not contain a method/modality column.",
            )

        modality_text = modality.strip()

        method_match = pd.Series(
            False,
            index=results.index,
        )

        campus_match = pd.Series(
            False,
            index=results.index,
        )

        if method_column is not None:
            method_match = (
                results[method_column]
                .fillna("")
                .astype(str)
                .str.contains(
                    modality_text,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        if campus_column is not None:
            campus_match = (
                results[campus_column]
                .fillna("")
                .astype(str)
                .str.contains(
                    modality_text,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        results = results[
            method_match | campus_match
        ]

    records = dataframe_to_records(results)

    return {
        "count": len(records),
        "filters": {
            "term": term,
            "department": department,
            "modality": modality,
        },
        "courses": records,
    }


@app.get("/sections")
def get_sections(
    course: str | None = Query(default=None),
    crn: str | None = Query(default=None),
    term: str | None = Query(default=None),
    modality: str | None = Query(default=None),
):
    results = courses.copy()

    if course:
        course_column = require_column(
            "COURSE",
            "COURSE ID",
        )

        results = text_filter(
            results,
            course_column,
            course,
        )

    if crn:
        crn_column = require_column("CRN")

        results = results[
            results[crn_column]
            .fillna("")
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
            == str(crn).strip()
        ]

    if term:
        term_column = require_column("TERM")

        results = text_filter(
            results,
            term_column,
            term,
        )

    if modality:
        method_column = get_column(
            "METHOD",
            "INSTRUCTION METHOD",
            "INSTRUCTIONAL METHOD",
            "MODALITY",
        )

        campus_column = get_column("CAMPUS")

        if method_column is None and campus_column is None:
            raise HTTPException(
                status_code=500,
                detail="The dataset does not contain a method/modality column.",
            )

        modality_text = modality.strip()

        method_match = pd.Series(
            False,
            index=results.index,
        )

        campus_match = pd.Series(
            False,
            index=results.index,
        )

        if method_column is not None:
            method_match = (
                results[method_column]
                .fillna("")
                .astype(str)
                .str.contains(
                    modality_text,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        if campus_column is not None:
            campus_match = (
                results[campus_column]
                .fillna("")
                .astype(str)
                .str.contains(
                    modality_text,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        results = results[
            method_match | campus_match
        ]

    records = dataframe_to_records(results)

    return {
        "count": len(records),
        "filters": {
            "course": course,
            "crn": crn,
            "term": term,
            "modality": modality,
        },
        "sections": records,
    }


@app.get("/alternatives")
def get_alternatives(
    crn: str = Query(..., pattern=r"^[0-9]+$"),
    selected_crns: str | None = Query(default=None),
):
    selected = []

    if selected_crns:
        selected = [
            value.strip()
            for value in selected_crns.split(",")
            if value.strip()
        ]

    try:
        alternatives = find_alternative_sections(
            courses,
            conflicted_crn=crn,
            selected_crns=selected,
            max_results=3,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    records = []

    for section in alternatives:
        record = {}

        for column in courses.columns:
            record[column] = clean_value(
                section[column]
            )

        records.append(record)

    if not records:
        return {
            "requested_crn": crn,
            "count": 0,
            "alternatives": [],
            "message": "No non-conflicting alternative sections were found.",
        }

    return {
        "requested_crn": crn,
        "count": len(records),
        "alternatives": records,
        "message": "Alternative sections found.",
    }


# The container copies the Vite build here. Mounting last preserves all API
# route precedence while making the reviewed artifact a single-origin app.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists() and os.getenv("SMARTADVISOR_SERVE_FRONTEND", "false").casefold() == "true":
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
