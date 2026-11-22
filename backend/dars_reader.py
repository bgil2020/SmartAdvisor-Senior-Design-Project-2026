
import re
import pymupdf


def extract_dars_information(pdf_bytes):
    with pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf"
    ) as pdf:
        text = "\n".join(
            page.get_text() for page in pdf
        )

    if not text.strip():
        raise ValueError(
            "The PDF does not contain readable text."
        )

    degree_match = re.search(
        r"B\.?\s*S\.?\s*in\s+Computer Science",
        text,
        re.IGNORECASE
    )

    return {
        "degree": (
            degree_match.group(0)
            if degree_match else None
        ),
        "raw_text": text
    }


def extract_semester_history(text):
    semesters = {}
    seen = set()

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    semester_names = {
        "01": "Spring",
        "05": "Summer",
        "08": "Fall"
    }

    grade_pattern = (
        r"(?:A|A-|B\+|B|B-|C\+|C|C-|"
        r"D\+|D|D-|F|S|U|P|W|I|--)"
        r"(?:\s*(?:EX|AV))?"
    )

    for i in range(len(lines) - 4):
        term, code, credits_text, grade = lines[i:i+4]

        if not re.fullmatch(r"\d{2}(01|05|08)", term):
            continue

        if not re.fullmatch(
            r"[A-Z]{2,4}\d{1,4}[A-Z]?", code
        ):
            continue

        if not re.fullmatch(r"\d+\.\d{2}", credits_text):
            continue

        if not re.fullmatch(grade_pattern, grade):
            continue

        title_index = i + 4

        if grade == "--" and title_index < len(lines):
            if lines[title_index] == "IP":
                title_index += 1

        if title_index >= len(lines):
            continue

        title = lines[title_index]

        if not re.search(r"[A-Za-z]", title):
            continue

        record_key = (
            term, code, credits_text, grade, title
        )

        if record_key in seen:
            continue

        seen.add(record_key)

        year = 2000 + int(term[:2])
        season = semester_names[term[-2:]]
        semester = f"{season} {year}"

        credits = float(credits_text)

        if grade == "--":
            status = "In Progress"
        elif credits == 0:
            status = "No Earned Credits"
        else:
            status = "Completed"

        course = {
            "course": code,
            "title": title,
            "credits": credits,
            "grade": grade,
            "status": status
        }

        semesters.setdefault(semester, []).append(course)

    def semester_sort_key(name):
        season, year = name.split()

        order = {
            "Spring": 1,
            "Summer": 2,
            "Fall": 3
        }

        return int(year), order[season]

    return dict(
        sorted(
            semesters.items(),
            key=lambda item: semester_sort_key(item[0])
        )
    )
