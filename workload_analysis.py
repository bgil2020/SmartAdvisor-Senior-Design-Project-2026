import re
def analyze_workload(syllabus_text):
    """Extract workload information from a syllabus."""

    text = syllabus_text.lower()

    # Extract grading percentages.
    grading_weights = {}

    for line in syllabus_text.splitlines():
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)

        if match:
            percentage = float(match.group(1))
            label = line[:match.start()].strip()

            # Remove decorative dots and separators.
            label = re.sub(r"[.…·_]+", " ", label).strip()

            if label:
                grading_weights[label] = percentage

    # Identify coursework using grading categories.
    # This avoids counting exam mentions in academic-integrity policies.
    labels = " ".join(grading_weights.keys()).lower()

    workload = {
        "homework": any(
    term in labels
    for term in ["homework", "assignment", "problem set"]
),
        "quizzes": "quiz" in labels,
        "exams": "exam" in labels or "test" in labels,
        "projects": "project" in labels,
        "grading_weights": grading_weights,
    }

    return workload