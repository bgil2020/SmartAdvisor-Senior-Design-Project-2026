
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")


def test_connection():
    if not url or not key:
        print("ERROR: Supabase URL or key is missing.")
        return

    try:
        supabase = create_client(url, key)

        response = (
            supabase.table("courses")
            .select("course_id")
            .limit(1)
            .execute()
        )

        print("Supabase connection successful!")
        print("Courses table is accessible.")
        print("No records were uploaded.")

    except Exception as error:
        print("Supabase connection failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Error code: {getattr(error, 'code', 'Unknown')}")
        print(f"Error message: {getattr(error, 'message', 'Unknown')}")


if __name__ == "__main__":
    test_connection()
