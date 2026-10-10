import pandas as pd

from .meeting_time_normalizer import normalize_days, online_section


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
    method = section.get("METHOD")

    if online_section(method):
        return False

    days = normalize_days(section.get("DAYS"))
    start = time_to_minutes(section.get("BEG TIME"))
    end = time_to_minutes(section.get("END TIME"))

    return bool(days) and start is not None and end is not None


def sections_overlap(section1, section2):
    if online_section(section1.get("METHOD")):
        return False

    if online_section(section2.get("METHOD")):
        return False

    days1 = set(normalize_days(section1.get("DAYS")))
    days2 = set(normalize_days(section2.get("DAYS")))

    common_days = days1.intersection(days2)

    if not common_days:
        return False

    start1 = time_to_minutes(section1.get("BEG TIME"))
    end1 = time_to_minutes(section1.get("END TIME"))

    start2 = time_to_minutes(section2.get("BEG TIME"))
    end2 = time_to_minutes(section2.get("END TIME"))

    if None in (start1, end1, start2, end2):
        return False

    return start1 < end2 and start2 < end1


def get_conflict_details(section1, section2):
    if not sections_overlap(section1, section2):
        return {
            "conflict": "No",
            "shared_days": "",
        }

    days1 = set(normalize_days(section1.get("DAYS")))
    days2 = set(normalize_days(section2.get("DAYS")))

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
    }