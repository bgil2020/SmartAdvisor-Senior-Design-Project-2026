
from pathlib import Path
import json
import math
import re
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "FAU_Courses.xlsx"
OUTPUT_DIR = BASE_DIR / "data" / "prepared"

REQUIRED_COLUMNS = [
    "CRN",
    "COURSE",
    "TITLE",
    "TERM",
    "SECT",
]


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_identifier(value):
    text = clean_text(value)

    if text.endswith(".0"):
        text = text[:-2]

    return text


def parse_integer(value):
    if pd.isna(value) or str(value).strip() == "":
        return None

    try:
        number = float(value)

        if not math.isfinite(number) or not number.is_integer():
            return None

        return int(number)

    except (ValueError, TypeError, OverflowError):
        return None


def parse_time(value):
    if pd.isna(value) or str(value).strip() == "":
        return None

    if hasattr(value, "hour") and hasattr(value, "minute"):
        return f"{value.hour:02d}:{value.minute:02d}:00"

    text = clean_text(value)

    for time_format in (
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
        "%H:%M:%S",
    ):
        try:
            return pd.to_datetime(
                text,
                format=time_format,
            ).strftime("%H:%M:%S")

        except (ValueError, TypeError):
            continue

    return None


def parse_credit_hours(value):
    text = clean_text(value)

    if not text:
        return None, None, None

    range_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)",
        text,
    )

    if range_match:
        minimum = float(range_match.group(1))
        maximum = float(range_match.group(2))

        if not (
            math.isfinite(minimum)
            and math.isfinite(maximum)
            and 0 <= minimum <= maximum <= 99.99
        ):
            raise ValueError("Invalid credit-hour range")

        return None, minimum, maximum

    try:
        hours = float(text)

        if not math.isfinite(hours) or not 0 <= hours <= 99.99:
            raise ValueError()

        return hours, None, None

    except (ValueError, TypeError):
        raise ValueError("Invalid credit hours")


def validate_and_prepare():
    if not DATA_FILE.exists():
        print(f"ERROR: Dataset not found: {DATA_FILE}")
        return

    dataframe = pd.read_excel(DATA_FILE)
    dataframe.columns = dataframe.columns.astype(str).str.strip()

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        print("Missing columns:", ", ".join(missing_columns))
        return

    courses_by_id = {}
    sections = []
    invalid_records = []
    course_warnings = []
    credit_hour_ranges = []
    seen_crns = set()

    credit_column = next(
        (
            name
            for name in (
                "CREDIT HOURS LOW:HIGH",
                "HOURS",
                "HOURS LOW",
                "CREDIT HOURS",
            )
            if name in dataframe.columns
        ),
        None,
    )

    for index, row in dataframe.iterrows():
        row_number = index + 2
        errors = []

        crn = clean_identifier(row.get("CRN"))
        course_id = clean_text(row.get("COURSE")).upper()
        title = clean_text(row.get("TITLE"))
        section_number = clean_identifier(row.get("SECT"))
        term = parse_integer(row.get("TERM"))
        seats = parse_integer(row.get("ENRL REMN"))

        for column, value in (
            ("CRN", crn),
            ("COURSE", course_id),
            ("TITLE", title),
            ("SECT", section_number),
        ):
            if not value:
                errors.append(f"Missing {column}")

        if term is None:
            errors.append("Invalid TERM")

        if crn:
            if crn in seen_crns:
                errors.append("Duplicate CRN")

            seen_crns.add(crn)

        if seats is None and clean_text(row.get("ENRL REMN")):
            errors.append("Invalid seats remaining")

        elif seats is not None and seats < 0:
            errors.append("Negative seats remaining")

        start_raw = row.get("BEG TIME")
        end_raw = row.get("END TIME")

        start_time = parse_time(start_raw)
        end_time = parse_time(end_raw)

        if clean_text(start_raw) and start_time is None:
            errors.append("Invalid start time")

        if clean_text(end_raw) and end_time is None:
            errors.append("Invalid end time")

        if start_time and end_time and end_time <= start_time:
            errors.append("End time must be after start time")

        department = clean_text(row.get("DEPT"))

        credit_hours = None
        min_credit_hours = None
        max_credit_hours = None

        if credit_column:
            try:
                (
                    credit_hours,
                    min_credit_hours,
                    max_credit_hours,
                ) = parse_credit_hours(row.get(credit_column))

            except ValueError as error:
                errors.append(str(error))

        course_record = {
            "course_id": course_id,
            "title": title,
            "department": department or None,
            "credit_hours": credit_hours,
        }

        section_record = {
            "crn": crn,
            "course_id": course_id,
            "term": term,
            "section_number": section_number,
            "campus": clean_text(row.get("CAMPUS")) or None,
            "days": clean_text(row.get("DAYS")) or None,
            "start_time": start_time,
            "end_time": end_time,
            "method": clean_text(row.get("METHOD")) or None,
            "seats_remaining": seats if seats is not None else 0,
            "enrollment_status": clean_text(
                row.get("ENRL STAT")
            ) or None,
        }

        if errors:
            invalid_records.append({
                "row": row_number,
                "crn": crn,
                "course_id": course_id,
                "errors": errors,
            })
            continue

        if min_credit_hours is not None:
            credit_hour_ranges.append({
                "row": row_number,
                "crn": crn,
                "course_id": course_id,
                "minimum_credit_hours": min_credit_hours,
                "maximum_credit_hours": max_credit_hours,
            })

        if course_id in courses_by_id:
            existing = courses_by_id[course_id]

            if existing != course_record:
                course_warnings.append({
                    "row": row_number,
                    "crn": crn,
                    "course_id": course_id,
                    "original_details": existing,
                    "different_details": course_record,
                })

        else:
            courses_by_id[course_id] = course_record

        sections.append(section_record)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_files = {
        "courses.json": list(courses_by_id.values()),
        "sections.json": sections,
        "invalid_records.json": invalid_records,
        "course_warnings.json": course_warnings,
        "credit_hour_ranges.json": credit_hour_ranges,
    }

    for filename, records in output_files.items():
        output_path = OUTPUT_DIR / filename

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(
                records,
                file,
                indent=2,
                ensure_ascii=False,
            )

    print(f"Total spreadsheet records: {len(dataframe)}")
    print(f"Prepared unique courses: {len(courses_by_id)}")
    print(f"Prepared sections: {len(sections)}")
    print(f"Excluded records: {len(invalid_records)}")
    print(f"Course detail warnings: {len(course_warnings)}")
    print(f"Variable-credit sections: {len(credit_hour_ranges)}")

    print("\nOutput files:")

    for filename in output_files:
        print(f"data/prepared/{filename}")

    print("\nPreparation complete. No data was uploaded.")


if __name__ == "__main__":
    validate_and_prepare()
