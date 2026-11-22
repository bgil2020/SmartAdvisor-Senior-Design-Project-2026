
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Depends
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .dars_reader import (
    extract_dars_information,
    extract_semester_history
)

router = APIRouter(prefix="/dars", tags=["DARS"])

security = HTTPBearer()

MAX_PDF_SIZE = 5 * 1024 * 1024


async def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    supabase_url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("VITE_SUPABASE_URL")
    )

    supabase_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )

    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase authentication is not configured."
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": supabase_key,
                    "Authorization": (
                        f"Bearer {credentials.credentials}"
                    )
                }
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable."
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session."
        )

    student = response.json()

    if not student.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Unable to verify student account."
        )

    return student


@router.post("/upload-preview")
async def upload_dars_preview(
    file: UploadFile = File(...),
    student: dict = Depends(get_current_student)
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    pdf_bytes = await file.read(MAX_PDF_SIZE + 1)

    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=413,
            detail="PDF must be smaller than 5 MB."
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file."
        )

    try:
        dars = extract_dars_information(pdf_bytes)
        history = extract_semester_history(
            dars["raw_text"]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Unable to parse the DARS PDF."
        ) from exc


    return {
        "account_id": student["id"],
        "degree": dars["degree"],
        "semesters": history
    }
