from datetime import datetime
from typing import Any, Dict, List, Optional


SCHEDULE_STATUS_SCHEDULED = "SCHEDULED"
SCHEDULE_STATUS_ASYNCHRONOUS = "VERIFIED_ASYNCHRONOUS"
SCHEDULE_STATUS_UNKNOWN = "UNKNOWN_TIMING"


def normalize_time(time_value):
    if time_value is None:
        return None

    time_text = str(time_value).strip()

    if not time_text:
        return None

    formats = [
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
        "%H%M",
    ]

    for time_format in formats:
        try:
            parsed_time = datetime.strptime(time_text.upper(), time_format)
            return parsed_time.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue

    return None


def normalize_days(days_value):
    if days_value is None:
        return []

    days_text = str(days_value).strip().upper()

    if not days_text:
        return []

    days_text = days_text.replace(" ", "")
    days_text = days_text.replace(",", "")

    valid_days = ["M", "T", "W", "R", "F", "S", "U"]

    normalized_days = []

    for day in days_text:
        if day in valid_days and day not in normalized_days:
            normalized_days.append(day)

    return normalized_days


def online_section(method_value):
    if method_value is None:
        return False

    method_text = str(method_value).strip().lower()

    online_methods = [
        "online",
        "distance learning",
        "asynchronous",
        "remote",
    ]

    for online_method in online_methods:
        if online_method in method_text:
            return True

    return False


def is_verified_asynchronous(section: Any) -> bool:
    """Determine whether a section is explicitly verified as asynchronous.

    Requirements:
    - Online delivery alone does not imply asynchronous.
    - Missing times alone does not imply asynchronous.
    - Requires an explicit asynchronous indicator (in method, title, delivery_mode, or attribute).
    """
    if section is None:
        return False

    if hasattr(section, "get"):
        method = str(section.get("METHOD") or "")
        title = str(section.get("TITLE") or "")
        delivery = str(section.get("DELIVERY_MODE") or "")
        is_async_flag = bool(section.get("is_asynchronous", False) or section.get("asynchronous", False))
    else:
        method = str(getattr(section, "method", "") or getattr(section, "METHOD", ""))
        title = str(getattr(section, "title", "") or getattr(section, "TITLE", ""))
        delivery = str(getattr(section, "delivery_mode", "") or getattr(section, "DELIVERY_MODE", ""))
        is_async_flag = bool(getattr(section, "is_asynchronous", False) or getattr(section, "asynchronous", False))

    if is_async_flag:
        return True

    combined = f"{method} {title} {delivery}".lower()
    return "asynchronous" in combined or "async" in combined


def get_schedule_status(section: Any) -> str:
    """Classify a section into one of three mutually exclusive scheduling states:
    1. SCHEDULE_STATUS_SCHEDULED: Has usable days and valid start/end times.
    2. SCHEDULE_STATUS_ASYNCHRONOUS: Explicitly verified asynchronous delivery.
    3. SCHEDULE_STATUS_UNKNOWN: Missing, TBA, or unverified timing information.
    """
    if section is None:
        return SCHEDULE_STATUS_UNKNOWN

    days_val = section.get("DAYS") if hasattr(section, "get") else getattr(section, "DAYS", None)
    beg_val = section.get("BEG TIME") if hasattr(section, "get") else getattr(section, "BEG TIME", None)
    end_val = section.get("END TIME") if hasattr(section, "get") else getattr(section, "END TIME", None)

    days = normalize_days(days_val)

    # Import time_to_minutes inside or parse here
    from .overlap_detector import time_to_minutes
    start_mins = time_to_minutes(beg_val)
    end_mins = time_to_minutes(end_val)

    # 1. Scheduled sections with usable days and times
    if days and start_mins is not None and end_mins is not None and start_mins < end_mins:
        return SCHEDULE_STATUS_SCHEDULED

    # 2. Explicitly verified asynchronous sections
    if is_verified_asynchronous(section):
        return SCHEDULE_STATUS_ASYNCHRONOUS

    # 3. Unknown / TBA / incomplete timing
    return SCHEDULE_STATUS_UNKNOWN


def normalize_meeting(days, start_time, end_time, method):
    online = online_section(method)

    normalized_days = normalize_days(days)
    normalized_start = normalize_time(start_time)
    normalized_end = normalize_time(end_time)

    if online and not normalized_days:
        days_output = "Online"
        normalized_start = None
        normalized_end = None
    else:
        days_output = ", ".join(normalized_days)

    return {
        "days": days_output,
        "start_time": normalized_start,
        "end_time": normalized_end,
        "online": "Yes" if online else "No",
    }