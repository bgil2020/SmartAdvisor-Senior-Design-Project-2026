
import time
import statistics

from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)

ENDPOINTS = [
    "/",
    "/courses",
    "/sections",
    "/alternatives?crn=99999999",
]

RUNS = 5


def test_api_response_times():
    print("\nSmartAdvisor API Performance Results")
    print("--------------------------------")

    for endpoint in ENDPOINTS:
        durations = []
        status_codes = []

        for _ in range(RUNS):
            start = time.perf_counter()
            response = client.get(endpoint)
            elapsed_ms = (time.perf_counter() - start) * 1000

            durations.append(elapsed_ms)
            status_codes.append(response.status_code)

        average_ms = statistics.mean(durations)
        maximum_ms = max(durations)

        print(
            f"{endpoint}: "
            f"average={average_ms:.2f} ms, "
            f"max={maximum_ms:.2f} ms, "
            f"statuses={status_codes}"
        )

        assert all(code < 500 for code in status_codes)

def test_compatibility_response_time():
    payload = {
        "student_id": "Z24567901",
        "proposed_courses": [
            "COP4331",
            "MAP3305",
            "CDA4630",
            "CEN4214",
        ],
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": [
            "CDA4240C",
            "CDA4102",
            "EEL3502",
            "MAC2313",
        ],
    }

    durations = []
    status_codes = []

    for _ in range(RUNS):
        start = time.perf_counter()
        response = client.post("/compatibility", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        durations.append(elapsed_ms)
        status_codes.append(response.status_code)

    average_ms = statistics.mean(durations)
    maximum_ms = max(durations)

    print(
        f"POST /compatibility: "
        f"average={average_ms:.2f} ms, "
        f"max={maximum_ms:.2f} ms, "
        f"statuses={status_codes}"
    )

    assert all(code == 200 for code in status_codes)

def test_conversation_response_time():
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": [
            "CDA4240C",
            "CDA4102",
            "MAC2313",
        ],
    }

    durations = []
    status_codes = []

    for _ in range(RUNS):
        start = time.perf_counter()
        response = client.post("/conversation", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        durations.append(elapsed_ms)
        status_codes.append(response.status_code)

        assert response.status_code == 200
        assert response.json()["status"] == "engine_executed"
        assert response.json()["engine_executed"] is True

    average_ms = statistics.mean(durations)
    maximum_ms = max(durations)

    print(
        f"POST /conversation: "
        f"average={average_ms:.2f} ms, "
        f"max={maximum_ms:.2f} ms, "
        f"statuses={status_codes}"
    )

    assert all(code == 200 for code in status_codes)
