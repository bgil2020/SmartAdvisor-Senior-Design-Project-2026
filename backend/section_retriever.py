from pathlib import Path
import pandas as pd


DEFAULT_DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "FAU_Courses.xlsx"
)


def load_course_data(file_path=DEFAULT_DATA_FILE):
    courses = pd.read_excel(file_path)

    required_columns = [
        "ENRL STAT",
        "TERM",
        "CRN",
        "COURSE",
        "SECT",
        "TITLE",
        "CAMPUS",
        "DAYS",
        "BEG TIME",
        "END TIME",
        "ENRL REMN",
        "INSTRUCTOR",
        "METHOD",
    ]

    missing = [
        column
        for column in required_columns
        if column not in courses.columns
    ]

    if missing:
        raise ValueError(
            "The course spreadsheet is missing required columns: "
            + ", ".join(missing)
        )

    text_columns = [
        "ENRL STAT",
        "CRN",
        "COURSE",
        "SECT",
        "TITLE",
        "CAMPUS",
        "DAYS",
        "BEG TIME",
        "END TIME",
        "INSTRUCTOR",
        "METHOD",
    ]

    for column in text_columns:
        courses[column] = (
            courses[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    courses["CRN"] = courses["CRN"].str.replace(
        r"\.0$",
        "",
        regex=True,
    )

    courses["SECT"] = courses["SECT"].str.replace(
        r"\.0$",
        "",
        regex=True,
    )

    courses["COURSE"] = courses["COURSE"].str.upper()

    courses["TERM"] = pd.to_numeric(
        courses["TERM"],
        errors="coerce",
    ).astype("Int64")

    courses["ENRL REMN"] = pd.to_numeric(
        courses["ENRL REMN"],
        errors="coerce",
    ).fillna(0).astype(int)

    return courses


def get_section_by_crn(courses, crn):
    crn = str(crn).strip().replace(".0", "")

    course_crns = (
        courses["CRN"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    result = courses[
        course_crns == crn
    ]

    if result.empty:
        return None

    return result.iloc[0]


def get_sections_for_course(
    courses,
    course_id,
    term=None,
):
    course_id = str(course_id).strip().upper()

    course_values = (
        courses["COURSE"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result = courses[
        course_values == course_id
    ]

    if term is not None:
        term_values = pd.to_numeric(
            result["TERM"],
            errors="coerce",
        )

        result = result[
            term_values == int(term)
        ]

    return result.copy()
