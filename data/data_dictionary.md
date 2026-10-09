
# SmartAdvisor Data Dictionary

## Purpose

This document defines the data structure for the SmartAdvisor academic planning prototype. It describes course, section, and student-profile information, including field names, data types, sources, requirements, and validation rules.

The course and section information comes from the FAU_Courses.xlsx dataset. Student profiles will use synthetic data for testing.

## 1. Course Table

Stores general information about courses.

| Field | Data Type | Required | Source | Validation |
|---|---|---|---|---|
| course_id (PK) | VARCHAR(20) | Yes | COURSE | Unique and not empty |
| title | VARCHAR(255) | Yes | TITLE | Cannot be empty |
| department | VARCHAR(20) | No | DEPT | Valid department code |
| credit_hours | DECIMAL(4,2) | No | HOURS | Must be 0 or greater |

## 2. Section Table

Stores available course sections and their scheduling information.

| Field | Data Type | Required | Source | Validation |
|---|---|---|---|---|
| crn (PK) | VARCHAR(20) | Yes | CRN | Unique and not empty |
| course_id (FK) | VARCHAR(20) | Yes | COURSE | Must reference Course |
| term | INTEGER | Yes | TERM | Valid term code |
| section_number | VARCHAR(10) | Yes | SECT | Cannot be empty |
| campus | VARCHAR(100) | No | CAMPUS | Text value |
| days | VARCHAR(20) | No | DAYS | Valid meeting-day codes |
| start_time | TIME | No | BEG TIME | Valid time if provided |
| end_time | TIME | No | END TIME | Later than start time |
| method | VARCHAR(50) | No | METHOD | Valid instruction method |
| seats_remaining | INTEGER | No | ENRL REMN | Must be 0 or greater |
| enrollment_status | VARCHAR(20) | No | ENRL STAT | Open, closed, or unspecified |

## 3. StudentProfile Table

Stores synthetic student information for prototype testing.

| Field | Data Type | Required | Source | Validation |
|---|---|---|---|---|
| student_id (PK) | UUID | Yes | Synthetic | Unique identifier |
| major | VARCHAR(100) | Yes | Synthetic | Cannot be empty |
| academic_level | VARCHAR(30) | Yes | Synthetic | Undergraduate or Graduate |
| completed_courses | JSONB | No | Synthetic | Valid course-ID array |
| selected_crns | JSONB | No | Synthetic | Valid section-CRN array |

Student profiles are fictional and should not contain actual student identification information.

## 4. Table Relationships

- One Course can have multiple Sections.
- Each Section belongs to one Course.
- Each Section references Course using course_id.
- StudentProfile stores selected CRNs for the initial prototype.
- A future implementation may use a separate student-section selection table.

## 5. Meeting-Time Validation

- Days use M, T, W, R, F, S, and U.
- Meeting times are standardized before schedule comparison.
- In-person sections require usable meeting information for reliable conflict checking.
- Asynchronous online sections may have no fixed meeting times.
- Missing or invalid meeting times must be identified rather than assumed conflict-free.

## 6. Modality and Availability

- Instruction modality is determined from METHOD and, when needed, CAMPUS.
- Section availability is determined from ENRL REMN.
- Sections with no remaining seats are excluded from alternative recommendations.
- Online and in-person sections are handled according to their available meeting information.

## 7. Risk Validation

The final SmartAdvisor design will also include course compatibility and override eligibility rules.

These rules will require fields such as:

- Course pair
- Risk category
- Severity
- Explanation
- Recommended action

The exact risk-rule schema will be finalized with the team.

## 8. Open Data Questions

- Confirm whether CRNs are unique across all terms or only within a term.
- Confirm the permitted values for METHOD and enrollment status.
- Confirm whether synchronous online sections have fixed meeting times.
- Confirm student-profile fields required for override eligibility.
- Confirm compatibility-risk data requirements with the responsible teammate.

## 9. Current Implementation Status

Course retrieval, meeting-time normalization, conflict detection, and alternative-section search are implemented in the Python backend.

The tables described here are a proposed database schema. The Supabase tables and database import pipeline still need to be implemented and verified.
