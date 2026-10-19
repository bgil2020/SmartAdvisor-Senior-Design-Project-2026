import pandas as pd

from .meeting_time_normalizer import (
    normalize_days,
    online_section,
    get_schedule_status,
    SCHEDULE_STATUS_SCHEDULED,
    SCHEDULE_STATUS_ASYNCHRONOUS,
    SCHEDULE_STATUS_UNKNOWN,
)


def time_to_minutes(value):
    if value is None or pd.isna(value):
        return None

    if hasattr(value, "hour") and hasattr(value, "minute"):
        return int(value.hour) * 60 + int(value.minute)

    text = str(value).strip()

    if not text:
        return None

    for time_format in (
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
        "%H:%M:%S",
        "%H%M",
    ):
        try:
            parsed = pd.to_datetime(text, format=time_format)
            return parsed.hour * 60 + parsed.minute
        except (ValueError, TypeError):
            continue

    return None


def has_schedule_information(section):
    """Returns True if the section has usable days and start/end meeting times."""
    return get_schedule_status(section) == SCHEDULE_STATUS_SCHEDULED


def sections_overlap(section1, section2):
    """Calculates time overlap between two sections.

    - Synchronous online sections undergo normal overlap calculation.
    - Verified asynchronous sections have no fixed meeting times and do not overlap.
    - Sections with unknown/TBA times cannot confirm overlap (returns False).
    """
    status1 = get_schedule_status(section1)
    status2 = get_schedule_status(section2)

    if status1 == SCHEDULE_STATUS_ASYNCHRONOUS or status2 == SCHEDULE_STATUS_ASYNCHRONOUS:
        return False

    if status1 == SCHEDULE_STATUS_UNKNOWN or status2 == SCHEDULE_STATUS_UNKNOWN:
        return False

    days1 = set(normalize_days(section1.get("DAYS") if hasattr(section1, "get") else getattr(section1, "DAYS", None)))
    days2 = set(normalize_days(section2.get("DAYS") if hasattr(section2, "get") else getattr(section2, "DAYS", None)))

    common_days = days1.intersection(days2)

    if not common_days:
        return False

    start1 = time_to_minutes(section1.get("BEG TIME") if hasattr(section1, "get") else getattr(section1, "BEG TIME", None))
    end1 = time_to_minutes(section1.get("END TIME") if hasattr(section1, "get") else getattr(section1, "END TIME", None))

    start2 = time_to_minutes(section2.get("BEG TIME") if hasattr(section2, "get") else getattr(section2, "BEG TIME", None))
    end2 = time_to_minutes(section2.get("END TIME") if hasattr(section2, "get") else getattr(section2, "END TIME", None))

    if None in (start1, end1, start2, end2):
        return False

    return start1 < end2 and start2 < end1


def get_conflict_details(section1, section2):
    """Evaluates conflict details distinguishing confirmed conflict, confirmed no-conflict,
    verified asynchronous delivery, and uncertain timing due to missing/TBA schedules.
    """
    status1 = get_schedule_status(section1)
    status2 = get_schedule_status(section2)

    # 1. Unknown / TBA / incomplete timing -> Cannot produce a verified "no conflict"
    if status1 == SCHEDULE_STATUS_UNKNOWN or status2 == SCHEDULE_STATUS_UNKNOWN:
        unknown_secs = []
        if status1 == SCHEDULE_STATUS_UNKNOWN:
            c1 = str(section1.get("COURSE") if hasattr(section1, "get") else getattr(section1, "COURSE", "Section 1")).strip()
            s1 = str(section1.get("SECT") if hasattr(section1, "get") else getattr(section1, "SECT", "")).strip()
            unknown_secs.append(f"{c1} section {s1}".strip())
        if status2 == SCHEDULE_STATUS_UNKNOWN:
            c2 = str(section2.get("COURSE") if hasattr(section2, "get") else getattr(section2, "COURSE", "Section 2")).strip()
            s2 = str(section2.get("SECT") if hasattr(section2, "get") else getattr(section2, "SECT", "")).strip()
            unknown_secs.append(f"{c2} section {s2}".strip())

        return {
            "conflict": "Unknown",
            "shared_days": "",
            "schedule_status": "unknown_timing",
            "reason": f"Meeting times are missing, TBA, or unverified for: {', '.join(unknown_secs)}.",
        }

    # 2. Verified asynchronous delivery
    if status1 == SCHEDULE_STATUS_ASYNCHRONOUS or status2 == SCHEDULE_STATUS_ASYNCHRONOUS:
        return {
            "conflict": "No",
            "shared_days": "",
            "schedule_status": "verified_asynchronous",
            "note": "Section is explicitly verified asynchronous online with no fixed meeting times.",
        }

    # 3. Both sections scheduled: evaluate time overlap
    if not sections_overlap(section1, section2):
        return {
            "conflict": "No",
            "shared_days": "",
            "schedule_status": "confirmed_no_conflict",
        }

    days1 = set(normalize_days(section1.get("DAYS") if hasattr(section1, "get") else getattr(section1, "DAYS", None)))
    days2 = set(normalize_days(section2.get("DAYS") if hasattr(section2, "get") else getattr(section2, "DAYS", None)))

    shared_days = days1.intersection(days2)

    day_order = ["M", "T", "W", "R", "F", "S", "U"]

    ordered_days = [
        day
        for day in day_order
        if day in shared_days
    ]

    return {
        "conflict": "Yes",
        "shared_days": ", ".join(ordered_days),
        "schedule_status": "confirmed_conflict",
    }