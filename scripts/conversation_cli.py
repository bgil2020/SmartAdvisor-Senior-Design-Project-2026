#!/usr/bin/env python3
"""SmartAdvisor Conversational Terminal Testing Interface.

A developer-only CLI harness for testing the real /conversation HTTP endpoint.
Does not independently classify, dispatch, or execute backend engines.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path for optional local diagnostics
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# Approved synthetic profiles for developer convenience
SYNTHETIC_PROFILES: Dict[str, Dict[str, Any]] = {
    "Z24567901": {
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
        "description": "Synthetic CS Senior - High performance, low work hours",
    },
    "Z23640867": {
        "student_id": "Z23640867",
        "recent_difficulty": 4,
        "satisfied_with_performance": "no",
        "work_hours": 25.0,
        "preferred_max_credits": 12.0,
        "recent_courses": ["COP3014", "MAC2311"],
        "description": "Synthetic EE Junior (Emma Smith) - Heavy work, needs lighter load",
    },
    "Z23649212": {
        "student_id": "Z23649212",
        "recent_difficulty": 3,
        "satisfied_with_performance": "mostly",
        "work_hours": 15.0,
        "preferred_max_credits": 14.0,
        "recent_courses": ["MAD2104"],
        "description": "Synthetic CS Junior (Amanda Green) - Moderate difficulty",
    },
}


class ConversationHarness:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/conversation"
        self.timeout = timeout_seconds
        self.context: Dict[str, Any] = {}
        self.show_raw: bool = False

    def clear_context(self) -> None:
        self.context.clear()
        print("\n[CONTEXT] All student context cleared. Requests will be sent without student/workload context.\n")

    def show_context(self) -> None:
        print("\n=== Current Configured Synthetic Student Context ===")
        if not self.context:
            print("  (Empty - no context will be attached to requests)")
        else:
            for k, v in self.context.items():
                print(f"  {k}: {v}")
        print("====================================================\n")

    def load_synthetic_profile(self, profile_id: str) -> None:
        pid = profile_id.strip().upper()
        if pid not in SYNTHETIC_PROFILES:
            print(f"\n[ERROR] Unknown synthetic profile '{pid}'.")
            print("Available synthetic profiles:")
            for k, p in SYNTHETIC_PROFILES.items():
                print(f"  - {k}: {p.get('description', '')}")
            print()
            return

        data = SYNTHETIC_PROFILES[pid]
        self.context = {k: v for k, v in data.items() if k != "description"}
        print(f"\n[SYNTHETIC PROFILE LOADED] ID: {pid}")
        print(f"  Description: {data.get('description')}")
        print("  NOTICE: This is synthetic test data only. No real student data is used.")
        self.show_context()

    def set_context_field(self, field: str, value_str: str) -> None:
        field = field.strip()
        val_str = value_str.strip()

        if field in ("recent_difficulty", "term"):
            try:
                self.context[field] = int(val_str)
            except ValueError:
                print(f"[ERROR] '{field}' must be an integer.")
                return
        elif field in ("work_hours", "preferred_max_credits"):
            try:
                self.context[field] = float(val_str)
            except ValueError:
                print(f"[ERROR] '{field}' must be a numeric float.")
                return
        elif field in ("recent_courses", "sections"):
            self.context[field] = [c.strip().upper() for c in val_str.split(",") if c.strip()]
        elif field == "selected_sections":
            if val_str in ("[]", "empty", "none_enrolled"):
                self.context[field] = []
            else:
                self.context[field] = [c.strip().replace(".0", "") for c in val_str.split(",") if c.strip()]
        else:
            self.context[field] = val_str

        print(f"[CONTEXT] Set {field} = {self.context[field]}")

    def call_endpoint(self, message: str) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {"message": message}
        payload.update(self.context)

        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=req_body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        if self.show_raw:
            print("\n--- [DEBUG] Request JSON ---")
            print(json.dumps(payload, indent=2))
            print("----------------------------\n")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.status
                raw_data = resp.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8") if err.fp else ""
            print(f"\n[HTTP ERROR] Status: {err.code} {err.reason}")
            try:
                err_json = json.loads(err_body)
                print(json.dumps(err_json, indent=2))
            except Exception:
                print(err_body or "(no error response body)")
            print()
            return None
        except urllib.error.URLError as err:
            print(f"\n[CONNECTION ERROR] Backend unreachable at {self.base_url}")
            print(f"  Reason: {err.reason}")
            print("  Please check that the backend is running (`uvicorn backend.api:app --port 8000`).\n")
            return None
        except TimeoutError:
            print(f"\n[TIMEOUT ERROR] Request timed out after {self.timeout} seconds.\n")
            return None
        except Exception as err:
            print(f"\n[UNEXPECTED ERROR] {type(err).__name__}: {err}\n")
            return None

        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError as err:
            print(f"\n[DECODE ERROR] Invalid JSON from backend: {err}")
            print(f"Raw body: {raw_data}\n")
            return None

        if self.show_raw:
            print("\n--- [DEBUG] Raw Response JSON ---")
            print(json.dumps(parsed, indent=2))
            print("---------------------------------\n")

        return parsed

    def display_response(self, data: Dict[str, Any]) -> None:
        print("\n" + "=" * 60)
        print("SMARTADVISOR CONVERSATIONAL RESPONSE")
        print("=" * 60)
        print(f"Status           : {data.get('status')}")
        print(f"Disposition      : {data.get('disposition')}")
        print(f"Target Handler   : {data.get('target_handler')}")
        print(f"Response Code    : {data.get('response_code')}")
        print(f"Safe to Route    : {data.get('safe_to_route')}")
        print(f"Engine Executed  : {data.get('engine_executed')}")

        parser_source = data.get("parser_source")
        if parser_source:
            print(f"Parser Source    : {parser_source}")
        if data.get("fallback_used"):
            print("Fallback Used    : True")
            if data.get("fallback_reason"):
                print(f"Fallback Reason  : {data.get('fallback_reason')}")
        if data.get("model_id"):
            print(f"Model ID         : {data.get('model_id')}")

        extracted_courses = data.get("extracted_courses", [])
        if extracted_courses:
            print(f"Extracted Courses: {', '.join(extracted_courses)}")

        missing_context = data.get("missing_context", [])
        if missing_context:
            print(f"Missing Context  : {', '.join(missing_context)}")

        print("\nResponse Text:")
        print(f"  \"{data.get('response_text')}\"")

        guidance = data.get("actionable_guidance")
        if guidance:
            print("\nActionable Guidance:")
            print(f"  {guidance}")

        engine_result = data.get("engine_result")
        if engine_result:
            print("\nEngine Result Summary:")
            if engine_result.get("success"):
                print(f"  Success         : {engine_result.get('success')}")

                # 1. Course Compatibility Result
                if "assessment" in engine_result:
                    print(f"  Student ID      : {engine_result.get('student_id')} ({engine_result.get('student_name')})")
                    print(f"  Proposed Credits: {engine_result.get('proposed_credits')}")
                    print(f"  Assessment      : {engine_result.get('assessment')}")
                    matched = engine_result.get("matched_course_combinations", [])
                    if matched:
                        print(f"  Matched Combos  : {len(matched)} pairs evaluated")
                        for m in matched:
                            c1 = m.get("course_1", "")
                            c2 = m.get("course_2", "")
                            risk = m.get("personalized_guidance", m.get("risk_category", "N/A"))
                            print(f"    - {c1} + {c2}: {risk}")
                    recs = engine_result.get("recommendations", [])
                    if recs:
                        print("  Recommendations :")
                        for r in recs:
                            print(f"    * {r}")

                # 2. Schedule Conflict Result
                elif "has_conflict" in engine_result:
                    conf = engine_result.get("has_conflict")
                    if conf is True:
                        conf_str = "YES"
                    elif conf is False:
                        conf_str = "NO"
                    else:
                        conf_str = "UNCERTAIN / UNVERIFIED"
                    print(f"  Conflict Found  : {conf_str}")
                    if conf:
                        print(f"  Shared Days     : {engine_result.get('shared_days', 'N/A')}")
                    if engine_result.get("is_uncertain"):
                        print(f"  Uncertain Reason: {engine_result.get('reason')}")
                    s1 = engine_result.get("section_1", {})
                    s2 = engine_result.get("section_2", {})
                    print(f"  Section 1       : {s1.get('course')} sec {s1.get('section')} (CRN {s1.get('crn')}, {s1.get('days')} {s1.get('time')})")
                    print(f"  Section 2       : {s2.get('course')} sec {s2.get('section')} (CRN {s2.get('crn')}, {s2.get('days')} {s2.get('time')})")

                # 3. Alternative Sections Result
                elif "alternatives" in engine_result:
                    target = engine_result.get("target_section", {})
                    print(f"  Target Section  : {target.get('course')} sec {target.get('section')} (CRN {target.get('crn')}, {target.get('days')} {target.get('time')})")
                    alts = engine_result.get("alternatives", [])
                    print(f"  Alternatives    : {len(alts)} found")
                    for a in alts:
                        ver_flag = "" if a.get("timing_verified", True) else " [UNVERIFIED TIMING]"
                        print(f"    * CRN {a.get('crn')} - Sec {a.get('section')}: {a.get('days')} {a.get('time')} | Seats Open: {a.get('seats_remaining')} | Instr: {a.get('instructor')}{ver_flag}")
                    sched = engine_result.get("selected_schedule", [])
                    if sched:
                        print(f"  Avoided Schedule: {len(sched)} enrolled class(es)")
                        for sc in sched:
                            print(f"      - {sc.get('course')} sec {sc.get('section')} (CRN {sc.get('crn')})")

                limits = engine_result.get("limitations")
                if limits:
                    print("  Limitations     :")
                    for lim in limits:
                        print(f"    * {lim}")
            else:
                print(f"  Error: {engine_result.get('error')}")

        disclaimer = data.get("disclaimer")
        if disclaimer:
            print(f"\nDisclaimer: {disclaimer}")
        print("=" * 60 + "\n")

    def run_diagnostics(self, message: str) -> None:
        """Inspect internal classifier/extractor representation for diagnostic debugging.

        Explicitly marked as local diagnostic inspection to preserve boundary.
        """
        try:
            from backend.app.conversational.intent_classifier import classify_intent
            from backend.app.conversational.entity_extractor import extract_entities
            from backend.app.conversational.response_policy import build_conversation_response

            print("\n--- [LOCAL DIAGNOSTIC PARSER INSPECTION] ---")
            print("NOTE: These fields are internal to backend/app/conversational and not all exposed via API.")
            intent_res = classify_intent(message)
            print(f"Classifier Intent    : {intent_res.get('intent')}")
            print(f"Matched Rules        : {intent_res.get('matched_rules')}")
            print(f"Needs Clarification  : {intent_res.get('needs_clarification')}")

            entities_res = extract_entities(message)
            print(f"Extracted Codes      : {entities_res.get('course_codes')}")
            print(f"Section Identifiers  : {entities_res.get('section_identifiers')}")
            print(f"Modality Preference  : {entities_res.get('modality_preference')}")
            print(f"Schedule Constraints : {entities_res.get('schedule_constraints')}")
            print(f"Missing Parser Fields: {entities_res.get('missing_fields')}")
            print(f"Validation Errors    : {entities_res.get('validation_errors')}")

            policy_res = build_conversation_response(message)
            print(f"Policy Disposition   : {policy_res.get('disposition')}")
            print(f"Policy Target Handler: {policy_res.get('target_handler')}")
            print(f"Policy Response Code : {policy_res.get('response_code')}")
            print("--------------------------------------------\n")
        except Exception as e:
            print(f"[DIAGNOSTIC ERROR] Unable to run local diagnostics: {e}")

    def print_help(self) -> None:
        print(
            """
SmartAdvisor Terminal Testing Interface Commands:
  :help                      Show this help menu
  :context                   Inspect active synthetic context
  :load-synthetic <ID>       Load synthetic profile (e.g. Z24567901, Z23640867, Z23649212)
  :set <field> <value>       Set context field (e.g. :set work_hours 10, :set student_id Z24567901)
  :clear                     Clear all context fields
  :raw                       Toggle display of raw request/response JSON
  :diagnostics <msg>         Run local diagnostic parser inspection (internal view)
  :quit or :q                Exit the CLI

Important Architectural Notes:
- Each message is sent as an independent stateless HTTP request.
- The backend does not maintain multi-turn conversational session memory.
- If the system asks for clarification, a follow-up answer (e.g. '001') will
  be evaluated on its own unless you provide the full message or context.
"""
        )

    def interactive_loop(self) -> None:
        print("\n=======================================================")
        print("  SmartAdvisor Terminal Testing Interface (Developer CLI)")
        print(f"  Connecting to: {self.endpoint}")
        print("  Type ':help' for commands, ':load-synthetic Z24567901' for context, or ':quit' to exit.")
        print("=======================================================\n")

        while True:
            try:
                prompt_line = input("student> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not prompt_line:
                continue

            if prompt_line in (":quit", ":q", "exit", "quit"):
                print("Exiting.")
                break
            elif prompt_line == ":help":
                self.print_help()
            elif prompt_line == ":context":
                self.show_context()
            elif prompt_line == ":clear":
                self.clear_context()
            elif prompt_line == ":raw":
                self.show_raw = not self.show_raw
                print(f"[CLI] Show raw JSON is now: {'ON' if self.show_raw else 'OFF'}")
            elif prompt_line.startswith(":load-synthetic"):
                parts = prompt_line.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: :load-synthetic <PROFILE_ID> (e.g., Z24567901)")
                else:
                    self.load_synthetic_profile(parts[1])
            elif prompt_line.startswith(":set"):
                parts = prompt_line.split(maxsplit=2)
                if len(parts) < 3:
                    print("Usage: :set <field> <value> (e.g., :set work_hours 20)")
                else:
                    self.set_context_field(parts[1], parts[2])
            elif prompt_line.startswith(":diagnostics"):
                parts = prompt_line.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: :diagnostics <message>")
                else:
                    self.run_diagnostics(parts[1])
            else:
                resp = self.call_endpoint(prompt_line)
                if resp:
                    self.display_response(resp)


def main():
    parser = argparse.ArgumentParser(description="SmartAdvisor Conversational Terminal Testing Interface")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--message", help="Execute single message non-interactively and exit")
    parser.add_argument("--synthetic-profile", help="Preload a synthetic student profile (e.g. Z24567901)")
    parser.add_argument("--sections", help="Comma-separated section identifiers or CRNs to compare")
    parser.add_argument("--target-section", help="Target section to replace in alternative section search")
    parser.add_argument("--selected-sections", help="Enrolled schedule section CRNs (or '[]' for empty schedule)")
    parser.add_argument("--term", type=int, help="Term code for lookup (e.g. 202608)")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON request and response")
    parser.add_argument("--diagnostics", action="store_true", help="Run diagnostic parser on single message")

    args = parser.parse_args()

    harness = ConversationHarness(base_url=args.base_url)
    harness.show_raw = args.raw

    if args.synthetic_profile:
        harness.load_synthetic_profile(args.synthetic_profile)
    if args.sections:
        harness.set_context_field("sections", args.sections)
    if args.target_section:
        harness.set_context_field("target_section", args.target_section)
    if args.selected_sections is not None:
        harness.set_context_field("selected_sections", args.selected_sections)
    if args.term is not None:
        harness.set_context_field("term", str(args.term))

    if args.message:
        if args.diagnostics:
            harness.run_diagnostics(args.message)
        resp = harness.call_endpoint(args.message)
        if resp:
            harness.display_response(resp)
            sys.exit(0)
        else:
            sys.exit(1)

    harness.interactive_loop()


if __name__ == "__main__":
    main()
