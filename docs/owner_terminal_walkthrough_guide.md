# Owner Terminal Demonstration & Verification Guide (TASK-006 / TASK-007)

This walkthrough provides exact copy-and-paste commands to personally run, verify, and screenshot the stabilized conversational scheduling and compatibility backend.

> [!NOTE]
> **Evidence Status**: Executed by AG at commit `cede77307bd7c06fa10388b938c001e8ff2c29e2`; owner reproduction pending.
> All commands and outputs documented below were verified against a live local Uvicorn instance on port 8000 using Windows PowerShell.

---

## 1. Checkpoint & Environment Summary

- **Repository**: `SmartAdvisor-Senior-Design-Project-2026`
- **Branch**: `feature/conversational-scheduling-integration`
- **Verified Commit SHA**: `cede77307bd7c06fa10388b938c001e8ff2c29e2`
- **Working-Tree Status**: Clean code state (zero uncommitted production code changes).
- **Environment**: Windows PowerShell with Python 3.12 (`py -3.12`).
  - Required dependencies: `pip install -r requirements.txt` (FastAPI, Uvicorn, Pandas, Openpyxl, Pydantic, Pytest).
- **Authoritative Catalog Term**: `202608` (Fall 2026, from `data/FAU_Courses.xlsx`).
- **Catalog Snapshot Notice**: Specific seat counts (e.g. 8 seats open) and section numbers reflect the current dataset snapshot in `data/FAU_Courses.xlsx`.
- **Pre-LLM Checkpoint Notice**: These tests verify the deterministic rule-based router and entity extractor baseline. When provider-independent LLM parsing is introduced in the next task, this deterministic pipeline serves as the verified fallback.

---

## 2. Startup Instructions

> [!TIP]
> In the commands below, replace `<REPO_DIR>` with your local repository path (e.g., `D:\Projects\SmartAdvisor-Senior-Design-Project-2026` or your clone directory).

### Terminal 1: Backend Server Startup
Open PowerShell window 1 and run:
```powershell
cd <REPO_DIR>
py -3.12 -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
- **What Successful Startup Looks Like**:
  ```text
  INFO:     Started server process [PID]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  ```
- **How to Stop the Backend**: Press `Ctrl + C` in Terminal 1.

### Terminal 2: CLI Client Operations
Open PowerShell window 2 and navigate to the repository:
```powershell
cd <REPO_DIR>
```
- **Connection Failure Detection**: If the backend in Terminal 1 is not running, running any CLI command prints:
  ```text
  [CONNECTION ERROR] Backend unreachable at http://127.0.0.1:8000
    Reason: [WinError 10061] No connection could be made because the target machine actively refused it
  ```

---

## 3. Eleven Numbered Verification Tests

Run each command in **Terminal 2**.

---

### Group I: Scheduling Engine & Parser Coverage

#### Test 1: Known Overlapping Pair (Text-Only Parsing Showcase)
- **Plain-Language Purpose**: Demonstrate pure text extraction where course codes and section numbers are extracted directly from the prompt without structured context.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Do COP 3530C section 001 and MAC 2312 section 006 overlap?" --term 202608
  ```
- **Context Attached**: None (text-only message).
- **Engine Invocation**: Real scheduling engine invoked (`Engine Executed: True`).
- **Expected Key Response Fields**:
  - `Status           : engine_executed`
  - `Response Code    : SCHEDULE_CONFLICT_FOUND`
  - `Engine Executed  : True`
  - `Extracted Courses: COP3530C, MAC2312`
  - `Conflict Found   : YES`
  - `Shared Days      : T, R`
- **Failure Indicators**: `Conflict Found: NO` or `Engine Executed: False`.

---

#### Test 2: Known Non-Overlapping Pair (Structured-Context Assistance Showcase)
- **Plain-Language Purpose**: Demonstrate structured context precedence where message text does not repeat section numbers, and structured sections supply the necessary details.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Do these sections overlap?" --sections "20158,15637" --term 202608
  ```
- **Context Attached**: Sections `20158` (COP 3530C sec 001, TR 12:30-1:50) and `15637` (MAC 2312 sec 002, WF 12:00-1:50); Term `202608`.
- **Engine Invocation**: Real scheduling engine invoked (`Engine Executed: True`).
- **Expected Key Response Fields**:
  - `Status           : engine_executed`
  - `Response Code    : NO_SCHEDULE_CONFLICT`
  - `Engine Executed  : True`
  - `Conflict Found   : NO`
- **Failure Indicators**: `Conflict Found: YES` or `Response Code: SCHEDULE_CONFLICT_FOUND`.

---

#### Test 3: Alternative Section Search (Target & Schedule Avoidance)
- **Plain-Language Purpose**: Verify alternative search replaces a target section while filtering out candidate sections that conflict with the student's enrolled schedule.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Find another section of COP 3530C section 001" --target-section 20158 --selected-sections 15637 --term 202608
  ```
- **Context Attached**: Target section `20158` (COP 3530C sec 001); Enrolled schedule `15637` (MAC 2312 sec 002 on WF 12:00-1:50); Term `202608`.
- **Engine Invocation**: Real scheduling engine invoked (`Engine Executed: True`).
- **Expected Key Response Fields**:
  - `Status           : engine_executed`
  - `Response Code    : ALTERNATIVE_SECTIONS_FOUND`
  - `Engine Executed  : True`
  - `Alternatives    : 1 found`
  - Section 012 (CRN `20789`, F 02:00 PM - 03:50 PM, 8 seats open)
  - `Avoided Schedule: 1 enrolled class(es) - MAC 2312 sec 002 (CRN 15637)`
  *(Note: Candidate Section 011 on Friday 12:00-1:50 is correctly excluded because it overlaps with enrolled MAC 2312 section 002 on Friday).*
- **Failure Indicators**: Section 011 returned despite Friday overlap, or zero alternatives found.

---

### Group II: Defensive Scheduling Validation & Timing Safety

#### Test 4: More Than Two Sections Rejected (No Silent Truncation)
- **Plain-Language Purpose**: Verify that requests referencing >2 sections are rejected before engine execution rather than silently truncating to the first pair.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Do COP 3530C section 001, MAC 2312 section 002, and MAC 2312 section 006 overlap?" --sections "20158,15637,17077" --term 202608
  ```
- **Context Attached**: Three section CRNs `20158, 15637, 17077`.
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : clarification`
  - `Response Code    : EXCESS_SECTIONS_DETECTED`
  - `Engine Executed  : False`
  - `Missing Context  : two_sections_only`
- **Failure Indicators**: `Status: engine_executed`, `Engine Executed: True`, or a `NO_SCHEDULE_CONFLICT` response evaluating only the first two sections.

---

#### Test 5: Contradictory Message vs. Context Clarified
- **Plain-Language Purpose**: Verify that discrepancies between message text and structured context return targeted clarification before engine invocation.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Do COP 3530C section 001 and MAC 2312 section 006 overlap?" --sections "20158,15637" --term 202608
  ```
- **Context Attached**: Message text references section 006; structured sections specify section 002 (CRN `15637`).
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : clarification`
  - `Response Code    : CONTRADICTORY_SECTION_DETAILS`
  - `Engine Executed  : False`
  - `Missing Context  : consistent_sections`
  - Response explains: *"Message references MAC2312 section 006, but structured input specifies section 002 (CRN 15637)"*.
- **Failure Indicators**: Query proceeds to engine execution without catching the mismatch.

---

#### Test 6: Missing/TBA Meeting Time Returns Uncertainty
- **Plain-Language Purpose**: Verify that in-person sections with missing/TBA times return safe uncertainty rather than a false "no conflict" verdict.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Do CNT 4403 section 001 and COP 3530C section 001 overlap?" --sections "18077,20158" --term 202608
  ```
- **Context Attached**: Section `18077` (CNT 4403 sec 001, In-Person, TBA times) and `20158` (COP 3530C sec 001); Term `202608`.
- **Engine Invocation**: Real engine invoked (`Engine Executed: True`).
- **Expected Key Response Fields**:
  - `Status           : engine_executed`
  - `Response Code    : SCHEDULE_UNCERTAIN_TIMING`
  - `Engine Executed  : True`
  - `Conflict Found   : UNCERTAIN / UNVERIFIED`
  - `Uncertain Reason : Meeting times are missing, TBA, or unverified for: CNT 4403 section 001.`
- **Failure Indicators**: `Conflict Found: NO` or `Response Code: NO_SCHEDULE_CONFLICT`.

---

### Group III: Workload Compatibility Engine Handoff

#### Test 7: Complete Synthetic Student/Workload Context
- **Plain-Language Purpose**: Verify conversational dispatch to the course compatibility engine when complete synthetic student workload context is attached.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Can I take COP 4331 and MAP 3305 together?" --synthetic-profile Z24567901
  ```
- **Context Attached**: Synthetic Profile `Z24567901` (Evie Woods, Electrical Engineering, difficulty 1, satisfied: yes, work_hours: 5.0, preferred_max_credits: 15.0).
- **Engine Invocation**: Real compatibility engine invoked (`Engine Executed: True`).
- **Expected Key Response Fields**:
  - `Status           : engine_executed`
  - `Response Code    : COMPATIBILITY_EVALUATION_COMPLETE`
  - `Engine Executed  : True`
  - `Target Handler   : course_compatibility_engine`
  - `Assessment       : Potentially manageable based on the information provided`
- **Failure Indicators**: `Engine Executed: False` or `Status: clarification`.

---

#### Test 8: Missing Required Workload Context (No Engine Call)
- **Plain-Language Purpose**: Verify that compatibility intent is recognized, but execution is withheld until required student workload details are supplied.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Can I take COP 4331 and MAP 3305 together?"
  ```
- **Context Attached**: None.
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : clarification`
  - `Response Code    : MISSING_STUDENT_CONTEXT`
  - `Engine Executed  : False`
  - `Missing Context  : student_id, recent_difficulty, satisfied_with_performance, work_hours`
- **Failure Indicators**: `Engine Executed: True` or engine execution error due to null profile.

---

### Group IV: Capability Boundaries & Escalation

#### Test 9: Preliminary Online Override Screening (Backend Unavailable / Directed to UI)
- **Plain-Language Purpose**: Verify that online override requests safely return `engine_unavailable` and direct the student to the UI form component rather than claiming engine execution.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Am I eligible for an online override for COP 3530?"
  ```
- **Context Attached**: None.
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : engine_unavailable`
  - `Response Code    : OVERRIDE_DIRECTED_TO_UI`
  - `Engine Executed  : False`
  - `Safe to Route    : True`
  - `Response Text    : "Online course override screening is available in the Online Course Override Evaluator form below..."`
- **Failure Indicators**: Claiming successful override evaluation, or unhandled exception.

---

#### Test 10: Official Override Approval / Registration (Advisor Escalation)
- **Plain-Language Purpose**: Verify that official university actions (approving overrides, course registration) are escalated to human advisors.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "Can you approve an override and register me for COP 3530?"
  ```
- **Context Attached**: None.
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : escalation`
  - `Disposition      : advisor_escalation`
  - `Target Handler   : academic_advisor`
  - `Response Code    : ADVISOR_ESCALATION_REQUIRED`
  - `Engine Executed  : False`
  - `Safe to Route    : False`
- **Failure Indicators**: `Status: engine_executed` or claiming registration capability.

---

#### Test 11: Informational Policy Query (Inactive-RAG Boundary)
- **Plain-Language Purpose**: Verify that general university policy queries are recognized as future RAG candidates and safely held at the inactive boundary.
- **Exact Command**:
  ```powershell
  py -3.12 scripts/conversation_cli.py --message "What does the policy say about dropping a course?"
  ```
- **Context Attached**: None.
- **Engine Invocation**: Engine intentionally prevented (`Engine Executed: False`).
- **Expected Key Response Fields**:
  - `Status           : rag_inactive`
  - `Disposition      : future_rag_candidate`
  - `Target Handler   : future_informational_rag`
  - `Response Code    : FUTURE_RAG_NOT_AVAILABLE`
  - `Engine Executed  : False`
  - `Safe to Route    : False`
- **Failure Indicators**: Hallucinating policy text or calling scheduling/compatibility engines.

---

## 4. Screenshot Guidance for Weekly Reporting

Plan four primary screenshots and two optional evidence captures for your report:

| Screenshot | Source Tests | Content & Fields to Keep Visible | Caption |
|---|---|---|---|
| **A. Compatibility Engine Result** | Test 7 & Test 8 | Test 7 command with `--synthetic-profile Z24567901` showing `COMPATIBILITY_EVALUATION_COMPLETE`, `Assessment: Potentially manageable...`, and Test 8 showing `MISSING_STUDENT_CONTEXT`. | *Conversational course compatibility handoff: Complete synthetic profile Z24567901 executes the compatibility engine (Test 7); omitting profile context safely requests clarification without engine execution (Test 8).* |
| **B. Scheduling Conflict and Non-Conflict** | Test 1 & Test 2 | Top command + response for Test 1 (`Conflict Found: YES`, `Shared Days: T, R`) followed by Test 2 (`Conflict Found: NO`). Ensure `Response Code` and `Engine Executed: True` are visible. | *Deterministic conflict detection evaluating verified section meeting times: Section 001 (COP 3530C, TR 12:30-1:50) confirms an overlap with Section 006 (MAC 2312, TR 12:00-1:50) and confirms no overlap with Section 002 (MAC 2312, WF 12:00-1:50).* |
| **C. Alternative Section Results** | Test 3 | Command line, `Target Section: COP 3530C sec 001`, `Alternatives: 1 found` (CRN 20789 sec 012, F 02:00-03:50), and `Avoided Schedule: MAC 2312 sec 002`. | *Alternative section search replacing COP 3530C section 001 while avoiding the student's enrolled schedule (MAC 2312 section 002 on WF). Section 011 is excluded due to Friday overlap; Section 012 is returned as verified non-conflicting.* |
| **D. Safe Validation and Timing Uncertainty** | Test 4, 5 & 6 | Commands and outputs for Test 4 (`EXCESS_SECTIONS_DETECTED`), Test 5 (`CONTRADICTORY_SECTION_DETAILS`), and Test 6 (`SCHEDULE_UNCERTAIN_TIMING`, `Conflict Found: UNCERTAIN / UNVERIFIED`). | *Pre-engine safety defenses: Prevention of silent section truncation on >2 sections (Test 4), contradiction defense (Test 5), and fail-safe uncertainty on TBA meeting times (Test 6).* |
| **E. Optional: Capability Boundaries** | Test 9 & 10 | Command and response for Test 9 (`OVERRIDE_DIRECTED_TO_UI`, `engine_unavailable`) and Test 10 (`ADVISOR_ESCALATION_REQUIRED`, `escalation`). | *Safe capability boundaries: Preliminary override requests are directed to the UI evaluator form without false engine execution; official approval/registration requests escalate to academic advisors.* |
| **F. Optional: Regression Summary** | Pytest Suite | PowerShell window running `py -3.12 -m pytest tests/test_scheduling_risk_investigation.py` showing `16 passed`. | *Automated regression suite: 16 corrective tests verifying section truncation prevention, online synchronous overlap calculation, TBA uncertainty, and context contradiction defense.* |

---

## 5. Proving Engine Invocation via Automated Integration Tests

To inspect existing tests that assert real engine execution versus defensive interception:

```powershell
py -3.12 -m pytest tests/test_scheduling_risk_investigation.py -k "test_risk_b_online_synchronous or test_risk_d_execution_semantics or test_risk_e_unknown_time" -v
```

1. **`test_risk_b_online_synchronous_undergoes_normal_overlap`** ([test_scheduling_risk_investigation.py:L143-178](file:///d:/Projects/SmartAdvisor-Senior-Design-Project-2026/tests/test_scheduling_risk_investigation.py#L143-L178)):
   - **Real Engine Proof**: Asserts underlying engine function `sections_overlap` returns `True` for catalog sections CRN 16899 and 16900, and verifies `engine_result["has_conflict"] is True`.
2. **`test_risk_d_execution_semantics_consistency`** ([test_scheduling_risk_investigation.py:L318-380](file:///d:/Projects/SmartAdvisor-Senior-Design-Project-2026/tests/test_scheduling_risk_investigation.py#L318-L380)):
   - **Real Engine Proof**: Proves that valid conflict and compatibility queries set `engine_executed=True` and populate `engine_result.success=True`, while clarification, escalation, and inactive-RAG queries strictly set `engine_executed=False` and `engine_result=None`.
3. **`test_risk_e_unknown_time_in_selected_schedule_discloses_limitation`** ([test_scheduling_risk_investigation.py:L448-478](file:///d:/Projects/SmartAdvisor-Senior-Design-Project-2026/tests/test_scheduling_risk_investigation.py#L448-L478)):
   - **Real Engine Proof**: Executes `find_alternative_sections` directly against real catalog data with enrolled TBA course CRN 18077, confirming `has_unknown_schedule=True`.
4. **Distinction from Mocked Failures**:
   - `test_engine_exception_handling_clean_response` in [test_scheduling_risk_investigation.py:L480-505](file:///d:/Projects/SmartAdvisor-Senior-Design-Project-2026/tests/test_scheduling_risk_investigation.py#L480-505) uses `unittest.mock.patch` solely to simulate an unexpected internal engine crash and verify that stack traces do not leak to the user.
