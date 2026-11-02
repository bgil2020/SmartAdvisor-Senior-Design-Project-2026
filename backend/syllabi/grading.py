"""Optional grading-category extraction adapted from the peer prototype.

This does not estimate weekly workload, difficulty, compatibility, eligibility,
or the absence of an assessment type. It only reports categories explicitly
paired with percentages in supplied syllabus text.
"""
from __future__ import annotations

import re
from typing import Any


def extract_grading_categories(text: str) -> dict[str, Any]:
    weights: list[dict[str, Any]] = []
    for line_number, line in enumerate((text or "").splitlines(), start=1):
        for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%", line):
            percentage = float(match.group(1))
            if percentage > 100:
                continue
            label = re.sub(r"[.…·_:\-]+$", "", line[: match.start()].strip()).strip()
            if label:
                weights.append({"label": label, "percentage": percentage, "line_number": line_number})
    return {
        "kind": "explicit_grading_category_percentages",
        "categories": weights,
        "limitations": [
            "Categories without an explicit percentage are not reported.",
            "A missing category is unknown, not proof that the assessment type is absent.",
            "Percentages do not establish weekly workload, difficulty, compatibility, or eligibility.",
        ],
    }
