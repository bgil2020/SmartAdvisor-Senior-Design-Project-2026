"""Course Compatibility API router. Does not change scheduling endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from .compatibility_engine import evaluate_compatibility

router = APIRouter(tags=["Course Compatibility"])

class CompatibilityRequest(BaseModel):
    student_id: str
    proposed_courses: list[str] = Field(min_length=1)
    recent_difficulty: int = Field(ge=1, le=5)
    satisfied_with_performance: Literal["yes", "mostly", "no"]
    work_hours: float = Field(ge=0, le=80)
    preferred_max_credits: float | None = Field(default=None, ge=1, le=30)
    recent_courses: list[str] | None = None

@router.post("/compatibility")
def check_compatibility(request: CompatibilityRequest):
    try:
        result = evaluate_compatibility(**request.model_dump())
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=500, detail=f"Compatibility data unavailable: {exc}") from exc
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result
