from .section_retriever import (
    get_section_by_crn,
    get_sections_for_course,
)

from .overlap_detector import (
    sections_overlap,
    has_schedule_information,
)


def section_is_open(section):
    """
    A section is considered available when ENRL REMN
    is greater than zero.

    This works even when ENRL STAT is blank in the
    FAU spreadsheet.
    """

    try:
        return int(section["ENRL REMN"]) > 0
    except (TypeError, ValueError, KeyError):
        return False


def section_is_online(section):
    """
    Determine whether the section is an online course.

    FAU data may describe online courses using METHOD
    or CAMPUS information.
    """

    method = str(section.get("METHOD", "")).strip().lower()
    campus = str(section.get("CAMPUS", "")).strip().lower()

    online_words = (
        "online",
        "fully online",
        "distance learning",
        "remote",
        "web",
    )

    for word in online_words:
        if word in method or word in campus:
            return True

    return False


def find_alternative_sections(
    courses,
    conflicted_crn,
    selected_crns,
    max_results=3,
):
    

    conflicted_section = get_section_by_crn(
        courses,
        conflicted_crn,
    )

    if conflicted_section is None:
        raise ValueError(
            f"CRN {conflicted_crn} was not found."
        )

    course_id = conflicted_section["COURSE"]
    term = conflicted_section["TERM"]

    # --------------------------------------------------
    # Build the student's other selected classes
    # --------------------------------------------------

    other_selected = []

    for crn in selected_crns:

        crn = str(crn).strip()

        # Do not compare the class being replaced
        # against itself.
        if crn == str(conflicted_crn).strip():
            continue

        section = get_section_by_crn(
            courses,
            crn,
        )

        if section is not None:
            other_selected.append(section)

    # --------------------------------------------------
    # Find all other sections of the same course
    # --------------------------------------------------

    candidates = get_sections_for_course(
        courses,
        course_id=course_id,
        term=term,
    )

    alternatives = []

    # --------------------------------------------------
    # Check each possible alternative
    # --------------------------------------------------

    for _, candidate in candidates.iterrows():

        candidate_crn = str(
            candidate["CRN"]
        ).strip()

        if candidate_crn == str(conflicted_crn).strip():
            continue

        if not section_is_open(candidate):
            continue

        schedule_available = has_schedule_information(
            candidate
        )

        online = section_is_online(candidate)

        if not schedule_available and not online:
            continue

        # --------------------------------------------------
        # Check for conflicts
        # --------------------------------------------------

        conflicts = []

        # Online classes with no fixed meeting time do not
        # need a normal time-overlap check.
        if schedule_available:

            for selected in other_selected:

                if sections_overlap(
                    candidate,
                    selected,
                ):
                    conflicts.append(selected)

        # If a conflict was found, do not recommend it.
        if conflicts:
            continue

        # Candidate passed all checks.
        alternatives.append(candidate)



    
    alternatives.sort(
        key=lambda row: int(row["ENRL REMN"]),
        reverse=True,
    )

    # Return at most max_results alternatives.
    return alternatives[:max_results]