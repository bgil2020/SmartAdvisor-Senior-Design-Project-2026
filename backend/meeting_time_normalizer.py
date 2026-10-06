from datetime import datetime


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