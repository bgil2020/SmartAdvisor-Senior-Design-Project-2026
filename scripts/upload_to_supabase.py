
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "prepared"
BATCH_SIZE = 100


def load_records(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with open(path, "r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(f"{filename} must contain a list")

    return records


def validate_records(courses, sections):
    course_ids = [record["course_id"] for record in courses]
    section_crns = [record["crn"] for record in sections]

    if len(course_ids) != len(set(course_ids)):
        raise ValueError("Duplicate course IDs found")

    if len(section_crns) != len(set(section_crns)):
        raise ValueError("Duplicate section CRNs found")

    missing_courses = set(
        record["course_id"] for record in sections
    ) - set(course_ids)

    if missing_courses:
        raise ValueError(
            f"Sections reference missing courses: {missing_courses}"
        )


def upload_batches(client, table_name, records):
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]

        client.table(table_name).upsert(
            batch,
            on_conflict=(
                "course_id" if table_name == "courses" else "crn"
            ),
        ).execute()

        print(
            f"{table_name}: processed "
            f"{min(start + BATCH_SIZE, len(records))}/"
            f"{len(records)}"
        )


def main():
    try:
        courses = load_records("courses.json")
        sections = load_records("sections.json")

        validate_records(courses, sections)

        print(f"Prepared courses: {len(courses)}")
        print(f"Prepared sections: {len(sections)}")
        print("Validation passed.")

        if "--upload" not in sys.argv:
            print("\nPREVIEW ONLY: No data was uploaded.")
            print("Run with --upload when ready.")
            return

        confirmation = input(
            "\nType UPLOAD to confirm database changes: "
        )

        if confirmation != "UPLOAD":
            print("Upload cancelled.")
            return

        load_dotenv(BASE_DIR / ".env")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("Supabase URL or key is missing")

        client = create_client(url, key)

        print("\nUploading courses...")
        upload_batches(client, "courses", courses)

        print("\nUploading sections...")
        upload_batches(client, "sections", sections)

        course_count = (
            client.table("courses")
            .select("course_id", count="exact", head=True)
            .execute()
        )

        section_count = (
            client.table("sections")
            .select("crn", count="exact", head=True)
            .execute()
        )

        print("\nDatabase verification:")
        print(f"Courses in database: {course_count.count}")
        print(f"Sections in database: {section_count.count}")
        print("Upload completed.")

    except Exception as error:
        print(f"ERROR: {type(error).__name__}")
        print("The operation did not complete successfully.")
        print("Review the error before retrying.")


if __name__ == "__main__":
    main()
