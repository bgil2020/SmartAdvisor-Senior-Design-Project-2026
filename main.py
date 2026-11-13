from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="SmartAdvisor API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EvaluationRequest(BaseModel):
    major: str
    modality: str

class OverrideRequest(BaseModel):
    courseCode: str
    reason: str

class AlternativeRequest(BaseModel):
    courseCode: str

@app.post("/api/evaluate")
def evaluate_schedule(req: EvaluationRequest):
    conflicts = ["CS 101 and MATH 201 overlap on Mon/Wed from 10:00 to 10:30."]
    return {
        "riskScore": 65 if conflicts else 15,
        "riskLevel": "MEDIUM" if conflicts else "LOW",
        "conflicts": conflicts
    }

@app.post("/api/alternatives")
def get_alternatives(req: AlternativeRequest):
    if req.courseCode.upper() == "MATH 201":
        return {
            "alternatives": [
                {"id": "alt-1", "courseCode": "MATH 201-Sec 2", "title": "Calculus I (Alternative)", "schedule": "Tue/Thu 1:00 PM - 2:30 PM"},
                {"id": "alt-2", "courseCode": "MATH 201-Sec 3", "title": "Calculus I (Alternative)", "schedule": "Wed/Fri 3:00 PM - 4:30 PM"}
            ]
        }
    return {"alternatives": []}

@app.post("/api/override")
def submit_override(req: OverrideRequest):
    if not req.courseCode or not req.reason:
        raise HTTPException(status_code=400, detail="Missing course code or reason.")
    return {
        "status": "success",
        "message": f"Override request for {req.courseCode} successfully submitted to your academic advisor!"
    }
