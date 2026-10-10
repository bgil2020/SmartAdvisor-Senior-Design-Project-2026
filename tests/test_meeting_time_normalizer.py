from backend.meeting_time_normalizer import (
    normalize_time,
    normalize_days,
    online_section,
    normalize_meeting,
)


def test_standard_time():
    assert normalize_time("9:30 AM") == "9:30 AM"
    assert normalize_time("2:15 PM") == "2:15 PM"


def test_time_conversion():
    assert normalize_time("14:30") == "2:30 PM"
    assert normalize_time("09:00") == "9:00 AM"


def test_meeting_days():
    assert normalize_days("MWF") == ["M", "W", "F"]
    assert normalize_days("TR") == ["T", "R"]


def test_online_section():
    result = normalize_meeting(
        None,
        None,
        None,
        "Distance Learning",
    )

    assert result["days"] == "Online"
    assert result["start_time"] is None
    assert result["end_time"] is None
    assert result["online"] == "Yes"


def test_in_person_section():
    result = normalize_meeting(
        "MWF",
        "9:00 AM",
        "9:50 AM",
        "In-Person",
    )

    assert result["days"] == "M, W, F"
    assert result["start_time"] == "9:00 AM"
    assert result["end_time"] == "9:50 AM"
    assert result["online"] == "No"


def test_invalid_time():
    assert normalize_time("bad time") is None
    assert normalize_time("") is None
    assert normalize_time(None) is None