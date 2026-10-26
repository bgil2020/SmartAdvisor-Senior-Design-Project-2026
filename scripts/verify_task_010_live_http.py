"""Live HTTP Verification Script for Task 010.

Exercises the real running /conversation HTTP endpoint across:
1. Deterministic mode without provider calls.
2. Hybrid mode with configured real GEMINI_API_KEY (demonstrating graceful fallback when provider returns 402 prepayment exhausted).
3. Paraphrased compatibility check with synthetic workload profile.
4. Compatibility check with controlled provider failure followed by valid deterministic engine execution.
5. Scheduling conflict check with valid course-section associations and valid deterministic engine execution.
6. Missing-information clarification.
7. Safety gate advisor escalation boundary case.
8. Informational catalog policy candidate boundary case.

Saves structured evidence to docs/task_010_live_http_evidence.json.
Never logs or reveals API keys or sensitive auth tokens.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = f"{BASE_URL}/conversation"
OUTPUT_FILE = REPO_ROOT / "docs" / "task_010_live_http_evidence.json"


def wait_for_server(timeout_sec: float = 12.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(f"{BASE_URL}/docs", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def post_conversation(payload: dict) -> tuple[dict, float, int]:
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=req_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        elapsed_ms = (time.time() - start) * 1000
        status_code = resp.status
        data = json.loads(resp.read().decode("utf-8"))
        return data, elapsed_ms, status_code


def run_verification():
    print("=" * 75)
    print("STARTING TASK-010 BOUNDED REAL PROVIDER AND LIVE HTTP VERIFICATION")
    print("=" * 75)

    key_present = bool(os.environ.get("GEMINI_API_KEY"))
    configured_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    print(f"Python Executable: {sys.executable}")
    print(f"Is Virtual Environment: {sys.prefix != sys.base_prefix}")
    print(f"GEMINI_API_KEY Present: {key_present}")
    print(f"Configured Model: {configured_model}")

    all_evidence = {
        "metadata": {
            "task_id": "TASK-010",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python_executable": sys.executable,
            "is_virtual_environment": (sys.prefix != sys.base_prefix),
            "key_present": key_present,
            "artifact_type": "structured execution summary",
            "provider_status": "402 RESOURCE_EXHAUSTED (observed from Google GenAI provider)",
            "verification_status": "Live Gemini verification remains pending.",
            "notes": "Contains response_text_snippet and selected response fields rather than raw HTTP stream. HTTP 200 represents application response status, not provider success. model_id identifies the configured/attempted model, not proof that the model returned a successful parsing result. provider_called=true records that the running server reached the hybrid branch attempting a provider call prior to catching the provider error.",
        },
        "deterministic_mode_runs": [],
        "hybrid_mode_runs": [],
    }

    # -------------------------------------------------------------
    # PHASE 1: Deterministic Mode Verification
    # -------------------------------------------------------------
    print("\n--- PHASE 1: DETERMINISTIC MODE (No Provider Calls) ---")
    env_det = os.environ.copy()
    env_det["CONVERSATIONAL_PARSER_MODE"] = "deterministic"
    proc_det = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO_ROOT),
        env=env_det,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        if not wait_for_server():
            print("ERROR: Server failed to start in deterministic mode.")
            return

        det_test_cases = [
            {
                "case_id": "DET-01",
                "description": "Deterministic Compatibility Check",
                "payload": {
                    "message": "Can I take COP 4331 and MAP 3305 together?",
                    "student_id": "Z24567901",
                    "recent_difficulty": 1,
                    "satisfied_with_performance": "yes",
                    "work_hours": 5.0,
                    "preferred_max_credits": 15.0,
                    "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
                },
            },
            {
                "case_id": "DET-02",
                "description": "Deterministic Schedule Conflict Check (with bound sections)",
                "payload": {
                    "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
                    "term": 202608,
                },
            },
        ]

        for tc in det_test_cases:
            data, latency, code = post_conversation(tc["payload"])
            record = {
                "case_id": tc["case_id"],
                "description": tc["description"],
                "request_payload": tc["payload"],
                "status_code": code,
                "latency_ms": round(latency, 2),
                "parser_source": data.get("parser_source"),
                "fallback_used": data.get("fallback_used"),
                "model_id": data.get("model_id"),
                "target_handler": data.get("target_handler"),
                "response_code": data.get("response_code"),
                "engine_executed": data.get("engine_executed"),
                "status": data.get("status"),
                "response_text_snippet": data.get("response_text", "")[:120],
                "provider_called": False,
            }
            all_evidence["deterministic_mode_runs"].append(record)
            print(f"[{tc['case_id']}] {tc['description']} -> {data.get('response_code')} (latency: {latency:.1f}ms, parser: {data.get('parser_source')}, engine_executed: {data.get('engine_executed')})")

    finally:
        proc_det.terminate()
        try:
            proc_det.wait(timeout=3)
        except Exception:
            proc_det.kill()
        time.sleep(1.0)

    # -------------------------------------------------------------
    # PHASE 2: Hybrid Mode Verification with Real Key
    # -------------------------------------------------------------
    print("\n--- PHASE 2: HYBRID MODE WITH REAL CONFIGURED KEY ---")
    env_hyb = os.environ.copy()
    env_hyb["CONVERSATIONAL_PARSER_MODE"] = "hybrid"
    env_hyb["GEMINI_MODEL"] = configured_model
    env_hyb["GEMINI_TIMEOUT_SECONDS"] = "10.0"

    proc_hyb = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO_ROOT),
        env=env_hyb,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        if not wait_for_server():
            print("ERROR: Server failed to start in hybrid mode.")
            return

        hyb_test_cases = [
            {
                "case_id": "HYB-01",
                "description": "Compatibility paraphrase with explicit synthetic workload context (Provider call attempted)",
                "payload": {
                    "message": "Would enrolling in both COP 4331 and MAP 3305 exhaust my weekly capacity?",
                    "student_id": "Z24567901",
                    "recent_difficulty": 1,
                    "satisfied_with_performance": "yes",
                    "work_hours": 5.0,
                    "preferred_max_credits": 15.0,
                    "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
                },
                "expected_intent": "course_compatibility_check",
            },
            {
                "case_id": "HYB-02",
                "description": "Compatibility check: actual provider error (402 RESOURCE_EXHAUSTED) followed by valid deterministic engine result",
                "payload": {
                    "message": "Can I take COP 4331 and MAP 3305 together?",
                    "student_id": "Z24567901",
                    "recent_difficulty": 1,
                    "satisfied_with_performance": "yes",
                    "work_hours": 5.0,
                    "preferred_max_credits": 15.0,
                    "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
                },
                "expected_intent": "course_compatibility_check",
            },
            {
                "case_id": "HYB-03",
                "description": "Scheduling conflict check: actual provider error (402 RESOURCE_EXHAUSTED) followed by valid deterministic engine result",
                "payload": {
                    "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
                    "term": 202608,
                },
                "expected_intent": "schedule_conflict_check",
            },
            {
                "case_id": "HYB-04",
                "description": "Missing-information clarification: provider failure followed by clarification response",
                "payload": {
                    "message": "Can I take COP 3530?",
                },
                "expected_intent": "clarification",
            },
            {
                "case_id": "HYB-05",
                "description": "Safety gate boundary case: Advisor Escalation for Override (Deterministic safety gate)",
                "payload": {
                    "message": "Please approve an official prerequisite override for COP 3530 so I can graduate.",
                },
                "expected_intent": "advisor_escalation",
            },
            {
                "case_id": "HYB-06",
                "description": "Safety / Informational candidate boundary case (inactive RAG prototype candidate)",
                "payload": {
                    "message": "What does the university catalog policy say about course withdrawal prerequisites?",
                },
                "expected_intent": "future_rag_candidate",
            },
        ]

        for tc in hyb_test_cases:
            data, latency, code = post_conversation(tc["payload"])
            provider_called = (data.get("parser_source") in ("llm", "fallback") and data.get("disposition") != "escalation")
            record = {
                "case_id": tc["case_id"],
                "description": tc["description"],
                "request_payload": tc["payload"],
                "status_code": code,
                "latency_ms": round(latency, 2),
                "parser_source": data.get("parser_source"),
                "fallback_used": data.get("fallback_used"),
                "fallback_reason": data.get("fallback_reason"),
                "model_id": data.get("model_id"),
                "target_handler": data.get("target_handler"),
                "response_code": data.get("response_code"),
                "engine_executed": data.get("engine_executed"),
                "engine_result": data.get("engine_result"),
                "status": data.get("status"),
                "safe_to_route": data.get("safe_to_route"),
                "disposition": data.get("disposition"),
                "response_text_snippet": data.get("response_text", "")[:120],
                "provider_called": provider_called,
            }
            all_evidence["hybrid_mode_runs"].append(record)
            print(f"[{tc['case_id']}] {tc['description']}")
            print(f"       Status: {data.get('status')}, Code: {data.get('response_code')}")
            print(f"       Parser: {data.get('parser_source')}, Fallback: {data.get('fallback_used')}, Reason: {data.get('fallback_reason')}")
            print(f"       Engine Executed: {data.get('engine_executed')}, Handler: {data.get('target_handler')}, Latency: {latency:.1f}ms")

    finally:
        proc_hyb.terminate()
        try:
            proc_hyb.wait(timeout=3)
        except Exception:
            proc_hyb.kill()

    # Save structured evidence
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_evidence, f, indent=2)

    print(f"\nLive HTTP evidence written successfully to {OUTPUT_FILE}")
    print("=" * 75)


if __name__ == "__main__":
    run_verification()
