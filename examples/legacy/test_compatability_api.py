from course_compatibility_engine import evaluate_compatibility
import json

result = evaluate_compatibility(
    student_id="Z24567901",
    proposed_courses=[
        "COP4331",
        "MAP3305",
        "CDA4630",
        "CEN4214"
    ],
    recent_difficulty=1,
    satisfied_with_performance="yes",
    work_hours=5,
    preferred_max_credits=15,
    recent_courses=[
        "CDA4240C",
        "CDA4102",
        "EEL3502",
        "MAC2313"
    ]
)

print(json.dumps(result, indent=2))