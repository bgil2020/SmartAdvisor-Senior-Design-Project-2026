def section_to_dict(section):
    """Convert a pandas row into a frontend/API-friendly dictionary."""
    return {
        "crn": str(section["CRN"]),
        "course": str(section["COURSE"]),
        "section": str(section["SECT"]),
        "title": str(section["TITLE"]),
        "term": int(section["TERM"]),
        "days": str(section["DAYS"]),
        "begin_time": str(section["BEG TIME"]),
        "end_time": str(section["END TIME"]),
        "campus": str(section["CAMPUS"]),
        "method": str(section["METHOD"]),
        "instructor": str(section["INSTRUCTOR"]),
        "seats_remaining": int(section["ENRL REMN"]),
    }


def build_alternative_response(conflicted_section, alternatives):
    """Build the structured result SmartAdvisor can later send to a frontend."""
    results = [section_to_dict(section) for section in alternatives]

    return {
        "course": str(conflicted_section["COURSE"]),
        "original_crn": str(conflicted_section["CRN"]),
        "original_section": str(conflicted_section["SECT"]),
        "alternative_count": len(results),
        "alternatives": results,
        "message": (
            f"Found {len(results)} open, non-conflicting alternative section(s)."
            if results
            else "No open, non-conflicting alternative sections were found."
        ),
    }


def print_alternatives(response):
    """Pretty console output for development/testing."""
    print("\n" + "=" * 65)
    print("SMARTADVISOR - ALTERNATIVE SECTION SEARCH")
    print("=" * 65)
    print(f"Course: {response['course']}")
    print(f"Original CRN: {response['original_crn']}")
    print(response["message"])

    if not response["alternatives"]:
        return

    for number, section in enumerate(response["alternatives"], start=1):
        print("\n" + "-" * 65)
        print(f"Alternative #{number}")
        print("-" * 65)
        print(f"Course:          {section['course']}")
        print(f"Title:           {section['title']}")
        print(f"Section:         {section['section']}")
        print(f"CRN:             {section['crn']}")
        print(f"Days:            {section['days'] or 'No fixed days'}")
        print(
            f"Time:            "
            f"{section['begin_time'] or 'N/A'} - "
            f"{section['end_time'] or 'N/A'}"
        )
        print(f"Campus:          {section['campus']}")
        print(f"Method:          {section['method']}")
        print(f"Instructor:      {section['instructor']}")
        print(f"Seats Remaining: {section['seats_remaining']}")
        print("Conflict Check:  Passed")
