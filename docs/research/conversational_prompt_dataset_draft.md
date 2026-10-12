# SmartAdvisor Conversational Sample Prompt and Expected-Response Dataset

**Prepared by:** Fareed Uddin  
**Project:** Group 7 SmartAdvisor  
**Status:** Draft for Team Review  
**Purpose:** Week 2 artifact for the task **“Create labeled sample prompt and expected-response dataset.”**

## Scope and status

This dataset provides testable conversational examples for SmartAdvisor’s four currently defined student-request intents:

1. `course_compatibility_check`
2. `schedule_conflict_check`
3. `alternative_section_search`
4. `online_override_screening`

It also includes clarification, unsupported-scope, and result-unavailable cases. Each example labels the expected intent, information available in the prompt, information that is missing when applicable, expected next action, and expected plain-language response behavior.

### Important assumptions and items not finalized

- **Intent labels are working labels.** The four labels above follow the September 6 conversational input/output contract, but final API names and schemas have not yet been finalized.
- **Structured request field names are not finalized.** This dataset uses conceptual field names only (for example, `course_codes`, `sections`, and `requested_course_code`) so that later work can map them to the final backend/API contract.
- **Course codes, sections, course titles, days, times, and modalities in examples are illustrative.** They are not confirmations that these courses/sections are available in the prototype data.
- **No prompt predetermines a risk score, conflict finding, available section, or override decision.** Those outcomes must be returned by the applicable backend engine and approved prototype data/rules.
- **Risk-result categories, detailed explanation fields, and whether alternatives accompany a risk result are not finalized.** Expected behavior therefore refers to explaining the backend result rather than assuming a specific result.
- **Online-override screening questions, criteria, and final outcome rules are not finalized.** The examples label the information present or absent and the expected response state (such as `needs_more_information`) without making an official eligibility decision.
- **Course/section identifier formats and meeting-time representation are pending confirmation.** Examples use the formats shown in the draft contract (for example, `COP 3530`, `section 001`) as temporary assumptions.
- **Frontend display behavior is pending confirmation.** The dataset identifies response behavior only; it does not prescribe final chat/UI layout.

## Labeling guide

| Field | Meaning |
|---|---|
| `ID` | Stable identifier for a future classifier/extraction test case. |
| `Intent label` | Working intent classification expected from the prompt. |
| `Student prompt` | Natural-language message a student may enter. |
| `Information present` | Conceptual information the conversational layer should recognize if possible. |
| `Missing / unclear information` | Information that prevents a reliable request, if any. |
| `Expected next action` | Route to the relevant engine, ask a focused clarification, or provide a safe fallback. |
| `Expected response behavior` | What the response should communicate; it is not a prewritten final UI response. |
| `Assumption / review note` | Temporary assumption or input that still needs team confirmation. |

## Dataset

| ID | Intent label | Student prompt | Information present | Missing / unclear information | Expected next action | Expected response behavior | Assumption / review note |
|---|---|---|---|---|---|---|---|
| SA-001 | `course_compatibility_check` | Can I take COP 3330 and CEN 4010 together? | Course codes: COP 3330, CEN 4010 | Semester/workload details are optional under the draft contract | Create a course-compatibility request with both course codes | Explain the returned risk result, its stated reason, and a recommended next step; include the decision-support limitation | Final risk-result categories and response fields are pending confirmation from Batsheva |
| SA-002 | `course_compatibility_check` | I am considering COP 3530, MAC 2312, and CEN 4010 next semester. Is that too much? | Course codes: COP 3530, MAC 2312, CEN 4010; possible workload concern; “next semester” | Specific semester identifier is not provided; assumed non-blocking unless backend requires it | Create a compatibility request preserving the full course list for engine pairing analysis | Explain returned warnings/recommendations for affected course pairings or the full combination; do not invent a workload judgment | The proposal says the compatibility engine creates pairings from selected courses; final multi-course request format is pending |
| SA-003 | `course_compatibility_check` | Would taking Calculus II with COP 3530 be risky? | Course code: COP 3530; course title: Calculus II | Exact course code for Calculus II is not supplied | Ask a focused clarification for the course code or confirm the intended catalog course before routing | State that SmartAdvisor needs the exact course code to compare the courses reliably | Mapping course titles to catalog codes is not yet finalized |
| SA-004 | `course_compatibility_check` | Is COP3530 and CEN4010 a bad combo if I also work 30 hours a week? | Course codes in compact format: COP3530, CEN4010; workload context: 30 work hours/week | None if compact code normalization is supported; otherwise code-format clarification | Normalize/confirm course-code format, then create a compatibility request with optional workload context | Explain the returned risk result and any available recommendation; do not assume employment hours are part of final risk rules | Support for compact course-code formatting and workload fields is a temporary assumption |
| SA-005 | `course_compatibility_check` | Are these classes too hard to take together? | General request for compatibility evaluation | No course codes or class names | Ask for at least two course codes | Ask the student to provide the courses they are considering, with an example of the expected format | Required minimum of two course codes is defined in the draft contract |
| SA-006 | `course_compatibility_check` | Can I take COP 3330, CEN 4010, and whatever database class is required together? | Course codes: COP 3330, CEN 4010; an unclear course description | Exact database course code | Ask the student to identify the database course by course code before a complete request is created | Explain that a specific course code is needed to evaluate the full proposed combination | Course-title lookup behavior is not finalized |
| SA-007 | `schedule_conflict_check` | Do COP 3530 section 001 and MAC 2312 section 002 overlap? | Two course codes and section identifiers | None under the draft contract | Create a schedule-conflict request for both sections | State whether the backend found a conflict and identify overlapping day/time when returned | Section identifier format and final conflict-result fields are pending confirmation from Jeffrey |
| SA-008 | `schedule_conflict_check` | Will COP 3530-001 conflict with CEN 4010-003? | Two course/section pairs in hyphenated format | None if hyphenated format is accepted; otherwise format confirmation | Normalize/confirm identifiers and create a conflict request | State whether a conflict exists and identify affected sections/overlap when available | Hyphenated input normalization is an assumption for future extraction work |
| SA-009 | `schedule_conflict_check` | I have COP 3530 on Tuesday and Thursday from 3:30 to 4:45. Does it overlap with MAC 2312 from 4:00 to 5:15 on those days? | Course codes; days: Tuesday/Thursday; meeting-time ranges for both courses | Section identifiers are absent | If backend can compare supplied meeting times, create a time-based conflict request; otherwise ask for section identifiers | State whether the stated times overlap; if the system requires official section data, request section numbers instead | Whether direct meeting-time comparison is supported is not finalized |
| SA-010 | `schedule_conflict_check` | Does my Algorithms section overlap with Calculus? | General course titles | Exact course codes, section IDs, and meeting times | Ask for both course codes and section numbers; optionally accept meeting days/times if sections are unavailable | Ask a focused clarification instead of guessing which sections are meant | The draft contract requires section identifiers or meeting days/times |
| SA-011 | `schedule_conflict_check` | Can you check whether COP 3530 section 001 conflicts with my other classes? | One course/section pair | The other selected courses/sections or their meeting times | Ask the student to provide the other course sections or use the structured form if the schedule is already entered there | Explain what additional information is needed to compare schedules | Ability to reuse courses already entered in the frontend is not finalized |
| SA-012 | `schedule_conflict_check` | My classes meet on Monday at the same time. Is that a problem? | General conflict concern; day: Monday | Course/section identities and exact times | Ask for the affected course sections and/or specific meeting times | Request the details needed to identify the courses and verify overlap | No conflict finding should be assumed from a general statement alone |
| SA-013 | `alternative_section_search` | Is there another COP 3530 section that does not conflict with Calculus II? | Requested course: COP 3530; course to avoid conflict with: Calculus II | Exact code/section or meeting times for Calculus II may be needed | Create an alternative-section request if Calculus II can be resolved; otherwise ask for the course code/section or schedule constraint | List non-conflicting options returned by the backend; if none are returned, advise checking the official schedule or contacting an advisor | Course-title resolution and final alternative-result fields are pending confirmation |
| SA-014 | `alternative_section_search` | Find me a different section of COP 3530 that fits around MAC 2312 section 002. | Requested course: COP 3530; avoid-conflict course/section: MAC 2312 section 002 | None under draft contract | Create an alternative-section request | Present non-conflicting sections returned by the backend; state limitations if prototype data has no match | Final API fields for avoided sections are not finalized |
| SA-015 | `alternative_section_search` | Are there any online sections of COP 3530 that will work with my current schedule? | Requested course: COP 3530; modality preference: online; current schedule referenced | Actual current schedule details unless available through the structured frontend/session | Ask for the relevant existing sections or guide the student to the form if schedule context is not available | Explain that schedule details are needed before alternatives can be checked; once available, list returned matching options | Whether conversational context can access saved frontend schedule information is not finalized |
| SA-016 | `alternative_section_search` | I cannot take classes after 4 PM. Is there another section for COP 3330? | Requested course: COP 3330; schedule restriction: no classes after 4 PM | Day preferences and term may be optional; no current conflicting section is supplied | Create an alternative-section request if the backend accepts time restrictions; otherwise ask for the term or direct to the schedule form | Present sections that satisfy returned restrictions, or explain that no prototype match was found | Support for free-form time restrictions is not finalized; this is a useful extraction test case |
| SA-017 | `alternative_section_search` | Can you find me a better class? | Request for an alternative | Course to replace, reason/constraint, desired course area | Ask what course the student wants an alternative for and what problem they are trying to solve | Ask a focused clarification rather than selecting a course or recommendation independently | “Better” is too ambiguous to create a reliable request |
| SA-018 | `alternative_section_search` | COP 3530 is full. What else can I take instead this semester? | Requested course: COP 3530; full-section concern; term reference | Degree/program requirements, completed courses, and what type of alternative is wanted | Explain that this broader substitution/planning request needs more program information or advisor review; offer the standard form where applicable | Provide a safe scope-limitation response rather than inventing a degree-progress alternative | The current contract supports alternative sections, not confirmed degree-equivalent course substitution |
| SA-019 | `online_override_screening` | Can I take this course online because I work full time? | Circumstance: full-time work | Requested course; answers to approved override-screening questions | Begin/continue override screening and ask for the course plus the required screening information | Explain that SmartAdvisor needs additional information and that official advisor review is required | Override questions/criteria are pending confirmation from Batsheva |
| SA-020 | `online_override_screening` | I want to take COP 3330 online because I have a full-time job. Am I eligible for an override? | Requested course: COP 3330; circumstance: full-time job | Answers to remaining approved screening questions | Create a preliminary override-screening request if the contract permits partial requests; otherwise ask the next approved question | State that the system will screen the request based on required information; clearly note that advisor review is required | Final screening fields and whether partial requests are sent to backend are not finalized |
| SA-021 | `online_override_screening` | I need an online override for MAC 2312 because I have a medical issue. | Requested course: MAC 2312; stated circumstance: medical issue | Answers to approved screening questions; sensitive-detail handling guidance | Ask only the approved minimum follow-up information or direct the student to an advisor/official process if sensitive documentation is needed | Avoid requesting unnecessary sensitive details; state that official advisor review is required | Privacy workflow and approved medical-accommodation handling are not finalized; no real student data should be processed in prototype testing |
| SA-022 | `online_override_screening` | I answered all of the override questions. What happens if I am not eligible? | Override workflow context | Actual answers/result are not present | Explain the possible general next step: backend/advisor result is needed; when a not-eligible result is returned, alternatives or advisor guidance may be presented | Do not claim eligibility; explain that SmartAdvisor is decision support and official review remains required | Exact next steps for each override outcome are pending confirmation |
| SA-023 | `online_override_screening` | Can I get an online override? | General override request | Requested course, circumstance, and screening answers | Ask for the requested course and begin the approved screening questions | Request only the information required for the screening process and note advisor review | Required override-question sequence is not finalized |
| SA-024 | `clarification` | Can you check my schedule? | General request related to scheduling | Courses/sections or meeting days/times; whether student wants conflict check or alternatives | Ask whether the student wants a conflict check or alternative sections, then request the relevant courses/sections or times | Ask a short, focused question that moves the request into a supported intent | This is a classification-ambiguity case, not a backend request |
| SA-025 | `clarification` | I want help with COP 3530. | Course code: COP 3530 | User goal: risk, conflict, alternative section, or override | Ask what type of help is needed and offer the supported choices | Present concise options such as checking compatibility, checking a conflict, finding another section, or starting override screening | The UI’s final wording/menu design is pending frontend confirmation |
| SA-026 | `unsupported_scope` | Can you register me for COP 3530? | Request concerns course registration | Registration authorization and an official registration workflow | Explain that SmartAdvisor cannot register students; guide the student to the official registration system or advisor as appropriate | Provide a scope limitation without implying access to registration systems | Registration execution is outside the current prototype scope |
| SA-027 | `unsupported_scope` | What grade will I get if I take COP 3530 and CEN 4010? | Course codes; grade-prediction request | Grade-prediction inputs and an approved grade-prediction feature | Explain that SmartAdvisor can check course-combination risk but does not predict grades; offer a compatibility check instead | Do not produce a grade estimate | Grade prediction is outside the proposal’s defined core features |
| SA-028 | `result_unavailable` | Are there alternative COP 3530 sections that do not conflict with MAC 2312 section 002? | Requested course: COP 3530; avoid-conflict course/section: MAC 2312 section 002 | None at conversational-input stage | Create an alternative-section request; if backend/prototype data returns no result or is unavailable, use the result-unavailable fallback | Explain that no matching option was returned or the result could not be retrieved; recommend checking the official schedule or contacting an advisor | This labels expected behavior only; it does not assume whether alternatives exist in prototype data |

## Coverage check

| Coverage area | Included examples |
|---|---|
| Course compatibility / proposed course lists | SA-001 through SA-006 |
| Schedule conflicts | SA-007 through SA-012 |
| Alternative-section search | SA-013 through SA-018 and SA-028 |
| Online override screening | SA-019 through SA-023 |
| Clarification / ambiguous requests | SA-003, SA-005, SA-006, SA-010 through SA-012, SA-015, SA-017, SA-019 through SA-025 |
| Unsupported or out-of-scope requests | SA-026 through SA-027 |
| Result unavailable / no matching result | SA-028 |

**Total examples: 28**

## Out of scope for this artifact

This dataset does not implement:

- Intent-classification rules or accuracy measurements.
- Entity-extraction code, regexes, or tokenization rules.
- Final API endpoints, final JSON schema, or adapter code.
- Final response-template wording or frontend display design.
- Course-risk thresholds, override criteria, real schedule availability, or real student data.
- Automated unit tests.

Those items are planned in later SmartAdvisor tasks.