# SmartAdvisor API Specification

The SmartAdvisor backend is built with FastAPI and runs on `http://127.0.0.1:8000` by default.

---

## Base Configuration

- **Host & Port:** `127.0.0.1:8000`
- **Interactive Documentation:**
  - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
  - ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **CORS Allowed Origins:** `http://localhost:5173`, `http://127.0.0.1:5173`

---

## Endpoints

### 1. Health / Status Check

```http
GET /
```

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "message": "SmartAdvisor backend is running",
  "records_loaded": 913
}
```

---

### 2. Search Courses

```http
GET /courses?department=COP&term=202501
```

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `term` | string | No | Filter by term code (e.g. `202501`). |
| `department` | string | No | Filter by course prefix (e.g. `COP`, `EEL`, `CAP`). |
| `modality` | string | No | Filter by delivery modality (e.g. `In Person`, `Online`). |

**Response (`200 OK`):**
```json
{
  "count": 13,
  "courses": [
    {
      "COURSE": "CAP 2603",
      "TITLE": "Applied AI Tools and Tech",
      "DEPT": "CECS"
    }
  ],
  "filters": {
    "term": null,
    "department": "CAP",
    "modality": null
  }
}
```

---

### 3. Retrieve Course Sections

```http
GET /sections?course=CAP%204773
```

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `course` | string | No | Exact course code with space or without (e.g. `CAP 4773`, `COP3530`). |
| `crn` | string | No | Specific section CRN (e.g. `19417`). |
| `term` | string | No | Filter by academic term code. |
| `modality` | string | No | Filter by instructional modality. |

**Response (`200 OK`):**
```json
{
  "count": 5,
  "sections": [
    {
      "CRN": 18637,
      "COURSE": "CAP 4773",
      "SECT": "001",
      "TITLE": "Intro Data Science Analytics",
      "INSTRUCTOR": "Assis, Raquel",
      "DAYS": "T",
      "BEG TIME": "04:00 PM",
      "END TIME": "06:50 PM",
      "CAMPUS": "Boca Raton",
      "ENRL ACTL": 52,
      "ENRL REMN": 26,
      "METHOD": "In-Person"
    }
  ],
  "filters": {
    "course": "CAP 4773",
    "crn": null,
    "term": null,
    "modality": null
  }
}
```

---

### 4. Search Alternative Sections

Find non-conflicting alternative sections for a specified course section against the student's existing schedule.

```http
GET /alternatives?crn=19417&selected_crns=16817,19129
```

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `crn` | string | **Yes** | The CRN of the section with a scheduling conflict or needing replacement. |
| `selected_crns` | string | No | Comma-delimited list of other CRNs currently on the student's schedule. |

**Response (`200 OK`):**
```json
{
  "conflicted_crn": "19417",
  "course": "CAP 4773",
  "count": 2,
  "alternatives": [
    {
      "CRN": 18637,
      "COURSE": "CAP 4773",
      "SECT": "001",
      "INSTRUCTOR": "Assis, Raquel",
      "DAYS": "T",
      "BEG TIME": "04:00 PM",
      "END TIME": "06:50 PM",
      "METHOD": "In-Person"
    }
  ]
}
```

---

### 5. Evaluate Course Compatibility

Evaluates academic workload risk, credit limits, prior course experience, and known pairing heuristics.

```http
POST /compatibility
Content-Type: application/json
```

**Request Payload:**
```json
{
  "student_id": "Z24567901",
  "proposed_courses": ["COP4331", "MAP3305", "CDA4630", "CEN4214"],
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0,
  "preferred_max_credits": 15.0,
  "recent_courses": ["CDA4240C", "CDA4102", "EEL3502", "MAC2313"]
}
```

**Response (`200 OK`):**
```json
{
  "success": true,
  "student_id": "Z24567901",
  "student_name": "Evie Woods",
  "major": "Electrical Engineering",
  "proposed_courses": ["COP4331", "MAP3305", "CDA4630", "CEN4214"],
  "proposed_credits": 12.0,
  "recent_credits": 13.0,
  "assessment": "Potentially manageable based on the information provided",
  "matched_course_combinations": [],
  "completed_courses": ["ENC1101", "ENC1102", "MAC1105", "EEL3111", "STA4821"],
  "previously_completed_courses": [],
  "repeat_course_warning": null,
  "recommendations": [
    "Based on the student's reported experience, the proposed load appears reasonably consistent with a workload the student has previously managed successfully.",
    "Factors supporting the schedule: The proposed credit load is similar to the student's recent semester. The student reported that the recent semester felt very manageable."
  ],
  "data_warnings": [],
  "disclaimer": "This is preliminary academic planning guidance, not an official advising or registration decision."
}
```

---

### 6. Conversational Assistant (`POST /conversation`)

Evaluates natural language student prompts, extracts entities, and either dispatches the Course Compatibility Engine or returns deterministic guidance.

```http
POST /conversation
Content-Type: application/json
```

**Request Payload:**
```json
{
  "message": "Can I take COP 4331 and MAP 3305 together?",
  "student_id": "Z24567901",
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0,
  "preferred_max_credits": 15.0,
  "recent_courses": ["CDA4240C", "CDA4102"]
}
```

**Response (`200 OK` with Compatibility Engine Handoff):**
```json
{
  "status": "engine_executed",
  "raw_message": "Can I take COP 4331 and MAP 3305 together?",
  "disposition": "route_core_engine",
  "target_handler": "course_compatibility_engine",
  "response_code": "COMPATIBILITY_EVALUATION_COMPLETE",
  "response_text": "Workload compatibility evaluation completed for COP4331, MAP3305. Semester assessment: Potentially manageable based on the information provided.",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP4331", "MAP3305"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "student_id": "Z24567901",
    "student_name": "Evie Woods",
    "assessment": "Potentially manageable based on the information provided",
    "proposed_credits": 6.0,
    "disclaimer": "This is preliminary academic planning guidance, not an official advising or registration decision."
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

#### Key Conversational Status & Response Codes:
| `status` | `response_code` | Trigger Condition | Engine Executed? |
| :--- | :--- | :--- | :--- |
| `engine_executed` | `COMPATIBILITY_EVALUATION_COMPLETE` | Intent is compatibility check and all student context is supplied. | **Yes** |
| `clarification` | `MISSING_STUDENT_CONTEXT` | Compatibility intent recognized but student workload context is missing. | **No** |
| `clarification` | `AMBIGUOUS_REQUEST` | Query lacks courses or contains conflicting specifications. | **No** |
| `escalation` | `ADVISOR_ESCALATION_REQUIRED` | Intent touches official permissions, overrides, or policy exceptions. | **No** |
| `rag_inactive` | `FUTURE_RAG_NOT_AVAILABLE` | Informational query (syllabi, topics, campus resources). | **No** |
